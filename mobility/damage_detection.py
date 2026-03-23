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

# Main model deployment name in Azure
AZURE_MAIN_MODEL_DEPLOYMENT = os.environ["AZURE_MAIN_MODEL_DEPLOYMENT"]
# Example: "vehicle-inspector"

# Image generation deployment name in Azure
AZURE_IMAGE_DEPLOYMENT = os.environ["AZURE_IMAGE_DEPLOYMENT"]
# Example: "gpt-image-1.5"

client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=AZURE_OPENAI_BASE_URL.rstrip("/") + "/openai/v1/",
    default_headers={
        # Azure uses this header to select the image generation deployment
        "x-ms-oai-image-generation-deployment": AZURE_IMAGE_DEPLOYMENT,
        # Azure docs show this for preview image-generation behavior in Responses API examples
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
- Give pixel coordinates {x, y} for the hotspot marker center
- Give bounding region {x, y, width, height} of the affected area
- Assign color: "#E53935" (severe), "#FB8C00" (moderate), "#FDD835" (minor)
- Write a concise natural-language description including estimated size and depth

If no damage is found, return an empty array.

## TASK 4 — FEATURE HOTSPOT DETECTION
Identify all notable vehicle features visible in the image. For each:
- Assign a unique id (feat-001, feat-002, ...)
- Classify type (e.g., alloy_wheels, sunroof, roof_rack, fog_lights, led_headlights, premium_badge, spoiler, ...)
- Categorize: exterior_design | safety | technology | performance | convenience
- Provide confidence (0.0–1.0)
- Give pixel coordinates {x, y} for the hotspot marker center
- Use color "#1E88E5" for all feature markers
- Write a brief description of the feature

## TASK 5 — OVERALL SUMMARY
Provide:
- Total damage count and total feature count
- Overall condition: excellent | good | fair | poor
- Condition score: 1.0–10.0 (10 = perfect)

IMPORTANT RULES:
- All pixel coordinates must be relative to THIS image's dimensions.
- Be precise with spatial coordinates.
- Do not hallucinate damage that is not clearly visible. When uncertain, lower the confidence score.
- For angle detection, assume left-hand-drive (US market) when determining driver vs passenger side.
- Call the structured function exactly once for the JSON.
"""


WHITEBG_PROMPT = "Remove the background from this vehicle image and place the car on a pure white (#FFFFFF) background. Preserve all vehicle details exactly."


INSPECTION_TOOL = {
    "type": "function",
    "name": "return_vehicle_inspection",
    "description": "Return the vehicle inspection result as strict JSON.",
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
                            "front",
                            "front_driver_side",
                            "front_passenger_side",
                            "driver_side",
                            "passenger_side",
                            "rear_driver_side",
                            "rear_passenger_side",
                            "rear"
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
                        "position": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"}
                            },
                            "required": ["x", "y"]
                        },
                        "region": {
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
                        "position": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"}
                            },
                            "required": ["x", "y"]
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
                "required": [
                    "totalDamage", "totalFeatures", "overallCondition", "conditionScore"
                ]
            }
        },
        "required": [
            "angle", "carPosition", "damageHotspots", "featureHotspots", "summary"
        ]
    }
}


def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def draw_hotspots(base_image: Image.Image, inspection_json: dict, orig_size: tuple) -> Image.Image:
    """Draw damage and feature hotspot markers onto the white-background image.
    
    Coordinates in inspection_json are relative to orig_size (original image).
    They are scaled to match base_image dimensions before drawing.
    """
    img = base_image.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Scale factors from original image → white background image
    sx = img.width / orig_size[0]
    sy = img.height / orig_size[1]

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
        fill_rgba = hex_to_rgba(color_hex, alpha=55)
        border_rgba = hex_to_rgba(color_hex, alpha=220)

        # Circle at hotspot center — scale to white bg dimensions
        px = int(hotspot["position"]["x"] * sx)
        py = int(hotspot["position"]["y"] * sy)
        radius = 16
        draw.ellipse(
            [px - radius, py - radius, px + radius, py + radius],
            fill=border_rgba,
            outline=(255, 255, 255, 240),
            width=3,
        )

        # Label next to circle
        label = f"{hotspot['id']}  {hotspot['type'].replace('_', ' ')}"
        draw.text((px + radius + 6, py - 10), label, fill=border_rgba, font=font)

    return Image.alpha_composite(img, overlay).convert("RGB")


def generate_white_bg(image_path: str) -> bytes:
    """Call 1: send original image to image generation model, get white background image bytes."""
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
    """Call 2: run full inspection on the white background image directly.
    Coordinates returned are naturally relative to the white bg image.
    """
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


def inspect_vehicle_single_request(image_paths: list[str]):
    stem = Path(image_paths[0]).stem

    # Call 1: generate white background image from original
    print("Step 1/2: Generating white background image...")
    white_bg_bytes = generate_white_bg(image_paths[0])
    with open(f"{stem}_white_bg.png", "wb") as f:
        f.write(white_bg_bytes)

    # Call 2: run full inspection on white bg image — coords are naturally correct
    print("Step 2/2: Running inspection on white background image...")
    white_bg_b64 = base64.b64encode(white_bg_bytes).decode()
    inspection_json = inspect_white_bg(white_bg_b64)

    with open(f"{stem}_inspection.json", "w", encoding="utf-8") as f:
        json.dump(inspection_json, f, indent=2)

    # Draw annotations — no scaling needed, coords already match white bg image
    white_bg_img = Image.open(BytesIO(white_bg_bytes))
    annotated = draw_hotspots(white_bg_img, inspection_json, white_bg_img.size)
    annotated.save(f"{stem}_annotated.png")

    print(f"Saved {stem}_inspection.json")
    print(f"Saved {stem}_white_bg.png")
    print(f"Saved {stem}_annotated.png")
    return inspection_json


if __name__ == "__main__":
    IMAGE = "car.jpg"  # <-- change this to your image

    result = inspect_vehicle_single_request([IMAGE])
    print(json.dumps(result, indent=2))