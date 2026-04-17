import os
import json
import requests
from flask import Flask, render_template, request, jsonify
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CUISINES = [
    "No preference", "Italian", "Asian", "Mexican", "Mediterranean",
    "American", "Indian", "French", "Japanese", "Middle Eastern",
]

RESTRICTIONS = ["Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "Nut-free"]


def search_youtube(recipe_name: str) -> dict | None:
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return None
    query = f"{recipe_name} recipe cooking tutorial"
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 1,
        "key": api_key,
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()
        item = data.get("items", [None])[0]
        if not item:
            return None
        return {
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
        }
    except Exception:
        return None


@app.route("/")
def index():
    return render_template("index.html", cuisines=CUISINES, restrictions=RESTRICTIONS)


@app.route("/suggest", methods=["POST"])
def suggest():
    data = request.get_json()
    ingredients = data.get("ingredients", "").strip()
    cuisine = data.get("cuisine", "No preference")
    selected_restrictions = data.get("restrictions", [])

    if not ingredients:
        return jsonify({"error": "Ingredients are required."}), 400

    prompt = f"""You are a helpful cooking assistant. Based on the available ingredients and preferences below, suggest exactly 5 ranked recipes from best match to worst match.

Available ingredients: {ingredients}
Cuisine preference: {cuisine}
Dietary restrictions: {", ".join(selected_restrictions) if selected_restrictions else "None"}

Respond with a valid JSON array only — no markdown, no explanation outside the JSON. Each element must have:
- "name": recipe name (string)
- "description": one sentence description (string)
- "reason": why this ranks here given the ingredients and preferences (string)
- "ingredients_used": list of ingredients from the available list that this recipe uses (array of strings)"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    recipes = json.loads(raw)

    for recipe in recipes:
        video = search_youtube(recipe["name"])
        recipe["youtube_video_id"] = video["video_id"] if video else None
        recipe["youtube_title"] = video["title"] if video else None

    return jsonify({"recipes": recipes})


if __name__ == "__main__":
    app.run(debug=True)
