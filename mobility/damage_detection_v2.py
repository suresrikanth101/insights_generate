"""
damage_detection_v2.py  —  Option 2: Normalized coordinates (0.0–1.0)

Key difference from damage_detection.py:
  - Hotspot positions are returned as x_norm / y_norm (fractions of image dimensions)
    instead of raw pixel integers.
  - Models reason proportionally far better than in absolute pixels, improving accuracy.
  - At draw time, pixel coords are computed as:  px = x_norm * image_width
"""

import os
import json
import base64
from io import BytesIO
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

# -----------------------------------
# Azure OpenAI config
# -----------------------------------
AZURE_OPENAI_BASE_URL = os.environ["AZURE_OPENAI_BASE_URL"]
AZURE_OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
AZURE_MAIN_MODEL_DEPLOYMENT = os.environ["AZURE_MAIN_MODEL_DEPLOYMENT"]
AZURE_IMAGE_DEPLOYMENT = os.environ["AZURE_IMAGE_DEPLOYMENT"]

client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=AZURE_OPENAI_BASE_URL.rstrip("/") + "/openai/v1/",
    default_headers={
        "x-ms-oai-image-generation-deployment": AZURE_IMAGE_DEPLOYMENT,
        "api_version": "preview",
    },
)


def to_data_url(path: str) -> str:
    ext = Path(path).suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")
    b64 = base64.b64encode(Path(path).read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


# -----------------------------------
# Prompts
# -----------------------------------

WHITEBG_PROMPT = (
    "Remove the background from this vehicle image and place the car on a pure white "
    "(#FFFFFF) background. Preserve all vehicle details exactly."
)

YOUR_PROMPT = r"""
You are AutoSight, an expert automotive visual inspection AI. Analyze the attached vehicle image and return structured JSON metadata. Follow these instructions precisely:

## TASK 1 — ANGLE DETECTION
Classify the camera angle into exactly ONE of these canonical views:
- front (sortIndex: 1)
- front_driver_side (sortIndex: 2)
- front_passenger_side (sortIndex: 8)
- driver_side (sortIndex: 3)
- passenger_side (sortIndex: 7)
- rear_driver_side (sortIndex: 4)
- rear_passenger_side (sortIndex: 6)
- rear (sortIndex: 5)

Include a confidence score (0.0–1.0).

## TASK 2 — CAR POSITION METADATA
Determine:
- Bounding box: tightest rectangle around the entire vehicle as {x, y, width, height} in pixels
- Center point: centroid of the vehicle in pixels
- Vehicle coverage: what % of image width and height the vehicle occupies
- Visible panels: list all body panels visible in this view from this set:
  [hood, trunk, roof, front_bumper, rear_bumper, left_fender, right_fender,
   left_door_front, left_door_rear, right_door_front, right_door_rear,
   left_quarter_panel, right_quarter_panel, windshield, rear_window]

## TASK 3 — DAMAGE HOTSPOT DETECTION
Identify all visible damage areas on the vehicle. For each damage hotspot:
- Assign an id (e.g. dmg-001, dmg-002, ...)
- Classify type: scratch | dent | paint_chip | crack | rust | broken_part | misaligned_panel
- Rate severity: minor | moderate | severe
- Provide confidence (0.0–1.0)
- Map to the body panel it appears on
- Give NORMALIZED position {x_norm, y_norm} for the hotspot marker center:
    x_norm = horizontal center / image width   (0.0 = left edge, 1.0 = right edge)
    y_norm = vertical center   / image height  (0.0 = top edge,  1.0 = bottom edge)
- Give NORMALIZED bounding region {x_norm, y_norm, width_norm, height_norm}:
    x_norm, y_norm = top-left corner as fractions of image width/height
    width_norm     = region width  / image width
    height_norm    = region height / image height
- Assign color: "#E53935" (severe), "#FB8C00" (moderate), "#FDD835" (minor)
- Write a concise natural-language description including estimated size and depth

If no damage is found, return an empty array.

## TASK 4 — FEATURE HOTSPOT DETECTION
Identify all notable vehicle features visible in the image. For each:
- Assign a unique id (feat-001, feat-002, ...)
- Classify type (e.g., alloy_wheels, sunroof, roof_rack, fog_lights, led_headlights, premium_badge, spoiler, ...)
- Categorize: exterior_design | safety | technology | performance | convenience
- Provide confidence (0.0–1.0)
- Give NORMALIZED position {x_norm, y_norm} for the hotspot marker center (same definition as above)
- Use color "#1E88E5" for all feature markers
- Write a brief description of the feature

## TASK 5 — OVERALL SUMMARY
Provide:
- Total damage count and total feature count
- Overall condition: excellent | good | fair | poor
- Condition score: 1.0–10.0 (10 = perfect)

IMPORTANT RULES:
- All normalized coordinates must be relative to THIS image's dimensions (values between 0.0 and 1.0).
- Think proportionally: e.g. if the hood is in the left-center of the image, x_norm ≈ 0.30, y_norm ≈ 0.50.
- Be precise — small errors in norm coords cause visible misalignment.
- Do not hallucinate damage that is not clearly visible. When uncertain, lower the confidence score.
- For angle detection, assume left-hand-drive (US market) when determining driver vs passenger side.
- Call the structured function exactly once for the JSON.
"""

# -----------------------------------
# Tool schema — uses number (0.0–1.0) for position/region instead of integers
# -----------------------------------

INSPECTION_TOOL = {
    "type": "function",
    "name": "return_vehicle_inspection",
    "description": "Return the vehicle inspection result as strict JSON with normalized coordinates.",
    "strict": True,
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "angle": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "key": {
                        "type": "string",
                        "enum": [
                            "front", "front_driver_side", "front_passenger_side",
                            "driver_side", "passenger_side",
                            "rear_driver_side", "rear_passenger_side", "rear"
                        ]
                    },
                    "label": {"type": "string"},
                    "sortIndex": {"type": "integer"},
                    "confidence": {"type": "number"}
                },
                "required": ["key", "label", "sortIndex", "confidence"]
            },
            "carPosition": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "boundingBox": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"}
                        },
                        "required": ["x", "y", "width", "height"]
                    },
                    "center": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"}
                        },
                        "required": ["x", "y"]
                    },
                    "vehicleCoverage": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "widthPercent": {"type": "number"},
                            "heightPercent": {"type": "number"}
                        },
                        "required": ["widthPercent", "heightPercent"]
                    },
                    "visiblePanels": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["boundingBox", "center", "vehicleCoverage", "visiblePanels"]
            },
            "damageHotspots": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string"},
                        "severity": {"type": "string"},
                        "confidence": {"type": "number"},
                        "panel": {"type": "string"},
                        # Normalized position (0.0–1.0)
                        "position": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "x_norm": {"type": "number"},
                                "y_norm": {"type": "number"}
                            },
                            "required": ["x_norm", "y_norm"]
                        },
                        # Normalized region (0.0–1.0)
                        "region": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "x_norm": {"type": "number"},
                                "y_norm": {"type": "number"},
                                "width_norm": {"type": "number"},
                                "height_norm": {"type": "number"}
                            },
                            "required": ["x_norm", "y_norm", "width_norm", "height_norm"]
                        },
                        "color": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": [
                        "id", "type", "severity", "confidence", "panel",
                        "position", "region", "color", "description"
                    ]
                }
            },
            "featureHotspots": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string"},
                        "category": {"type": "string"},
                        "confidence": {"type": "number"},
                        # Normalized position (0.0–1.0)
                        "position": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "x_norm": {"type": "number"},
                                "y_norm": {"type": "number"}
                            },
                            "required": ["x_norm", "y_norm"]
                        },
                        "color": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": [
                        "id", "type", "category", "confidence",
                        "position", "color", "description"
                    ]
                }
            },
            "summary": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "totalDamage": {"type": "integer"},
                    "totalFeatures": {"type": "integer"},
                    "overallCondition": {"type": "string"},
                    "conditionScore": {"type": "number"}
                },
                "required": ["totalDamage", "totalFeatures", "overallCondition", "conditionScore"]
            }
        },
        "required": ["angle", "carPosition", "damageHotspots", "featureHotspots", "summary"]
    }
}


# -----------------------------------
# Drawing
# -----------------------------------

def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def draw_hotspots(base_image: Image.Image, inspection_json: dict) -> Image.Image:
    """Draw hotspot markers using normalized coords → converted to pixels at draw time."""
    img = base_image.convert("RGBA")
    W, H = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    all_hotspots = [
        *inspection_json.get("damageHotspots", []),
        *inspection_json.get("featureHotspots", []),
    ]

    for hotspot in all_hotspots:
        color_hex = hotspot["color"]
        border_rgba = hex_to_rgba(color_hex, alpha=220)

        # Convert normalized → pixel
        px = int(hotspot["position"]["x_norm"] * W)
        py = int(hotspot["position"]["y_norm"] * H)

        radius = 16
        draw.ellipse(
            [px - radius, py - radius, px + radius, py + radius],
            fill=border_rgba,
            outline=(255, 255, 255, 240),
            width=3,
        )

        label = f"{hotspot['id']}  {hotspot['type'].replace('_', ' ')}"
        draw.text((px + radius + 6, py - 10), label, fill=border_rgba, font=font)

    return Image.alpha_composite(img, overlay).convert("RGB")


# -----------------------------------
# LLM calls
# -----------------------------------

def generate_white_bg(image_path: str) -> bytes:
    """Call 1: generate white background image from original."""
    response = client.responses.create(
        model=AZURE_MAIN_MODEL_DEPLOYMENT,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": WHITEBG_PROMPT},
                {"type": "input_image", "image_url": to_data_url(image_path), "detail": "high"},
            ],
        }],
        tools=[{"type": "image_generation"}],
    )
    for item in response.output:
        if item.type == "image_generation_call" and getattr(item, "result", None):
            return base64.b64decode(item.result)
    raise RuntimeError("No white background image returned")


def inspect_white_bg(white_bg_b64: str) -> dict:
    """Call 2: run full inspection on white bg image with normalized coords."""
    response = client.responses.create(
        model=AZURE_MAIN_MODEL_DEPLOYMENT,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": YOUR_PROMPT},
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{white_bg_b64}",
                    "detail": "high",
                },
            ],
        }],
        tools=[INSPECTION_TOOL],
    )
    for item in response.output:
        if item.type == "function_call" and item.name == "return_vehicle_inspection":
            return json.loads(item.arguments)
    raise RuntimeError("No inspection JSON returned")


# -----------------------------------
# Main pipeline
# -----------------------------------

def inspect_vehicle(image_path: str):
    stem = Path(image_path).stem

    print(f"Step 1/2: Generating white background for {image_path}...")
    white_bg_bytes = generate_white_bg(image_path)
    with open(f"{stem}_white_bg.png", "wb") as f:
        f.write(white_bg_bytes)

    print("Step 2/2: Running inspection with normalized coordinates...")
    white_bg_b64 = base64.b64encode(white_bg_bytes).decode()
    inspection_json = inspect_white_bg(white_bg_b64)

    with open(f"{stem}_inspection.json", "w", encoding="utf-8") as f:
        json.dump(inspection_json, f, indent=2)

    # Draw — normalized coords converted to pixels inside draw_hotspots()
    white_bg_img = Image.open(BytesIO(white_bg_bytes))
    annotated = draw_hotspots(white_bg_img, inspection_json)
    annotated.save(f"{stem}_annotated.png")

    print(f"Saved {stem}_inspection.json")
    print(f"Saved {stem}_white_bg.png")
    print(f"Saved {stem}_annotated.png")
    return inspection_json


if __name__ == "__main__":
    IMAGE = "car.jpg"  # <-- change this to your image

    result = inspect_vehicle(IMAGE)
    print(json.dumps(result, indent=2))
