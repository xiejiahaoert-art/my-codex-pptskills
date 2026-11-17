"""Inspect original PowerPoint files and detect a loss of playback data."""

import argparse
import hashlib
import json
import posixpath
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def inspect(path):
    with ZipFile(path) as package:
        parts = set(package.namelist())
        presentation = ET.fromstring(package.read("ppt/presentation.xml"))
        relations = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in ET.fromstring(package.read("ppt/_rels/presentation.xml.rels"))
        }
        slides = []
        for slide_id in presentation.findall(f"./{P}sldIdLst/{P}sldId"):
            target = relations[slide_id.attrib[f"{R}id"]]
            part = target.lstrip("/") if target.startswith("/") else posixpath.normpath(
                posixpath.join("ppt", target)
            )
            root = ET.fromstring(package.read(part))
            nodes = root.findall(f"./{P}timing//{P}cTn")
            effects = Counter(
                (node.get("presetClass", ""), node.get("nodeType", ""), node.get("presetID", ""))
                for node in nodes if "presetID" in node.attrib
            )
            slides.append({
                "timing": bool(nodes),
                "transition": root.find(f".//{P}transition") is not None,
                "effects": sum(effects.values()),
                "effect_types": [{"preset_class": cls, "node_type": node_type, "preset_id": preset,
                                  "count": count}
                                 for (cls, node_type, preset), count in sorted(effects.items())],
                "video_targets": len(root.findall(f"./{P}timing//{P}video")),
                "interactive_sequences": sum(node.get("nodeType") == "interactiveSeq" for node in nodes),
                "replay_commands": sum(
                    cmd.get("cmd", "").startswith("playFrom(")
                    for seq in nodes if seq.get("nodeType") == "interactiveSeq"
                    for cmd in seq.findall(f".//{P}cmd")
                ),
            })
        show_props = "ppt/presProps.xml"
        show = ET.fromstring(package.read(show_props)).find(f"./{P}showPr") if show_props in parts else None
        media = sorted(part for part in parts if part.startswith("ppt/media/")
                       and Path(part).suffix.lower() in {".mp4", ".mov", ".m4v", ".wmv", ".avi", ".webm"})
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "show_animations": show is None or show.get("showAnimation", "true") not in {"0", "false"},
        "embedded_video_parts": media,
        "slide_count": len(slides),
        "slides": slides,
    }


def regressions(source, delivery):
    issues = []
    if source["slide_count"] != delivery["slide_count"]:
        issues.append("Slide count differs. The page comparison assumes the same slide order.")
    if len(source["embedded_video_parts"]) > len(delivery["embedded_video_parts"]):
        issues.append("Fewer embedded video parts.")
    if source["show_animations"] and not delivery["show_animations"]:
        issues.append("The show has disabled animations.")
    for index, (before, after) in enumerate(zip(source["slides"], delivery["slides"]), 1):
        for field in ("timing", "transition", "effects", "video_targets",
                      "interactive_sequences", "replay_commands"):
            if after[field] < before[field]:
                issues.append(f"Slide {index}: reduced {field}.")
        known_types = {(effect["preset_class"], effect["node_type"], effect["preset_id"])
                       for effect in after["effect_types"]}
        for effect in before["effect_types"]:
            if (effect["preset_class"], effect["node_type"], effect["preset_id"]) not in known_types:
                issues.append(f"Slide {index}: a source effect type or trigger mode is absent.")
                break
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("delivery", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        original = inspect(args.original)
        report = {"original": original}
        if args.delivery:
            delivery = inspect(args.delivery)
            report.update(delivery=delivery, byte_identical=original["sha256"] == delivery["sha256"],
                          possible_losses=regressions(original, delivery))
    except (OSError, BadZipFile, ET.ParseError, KeyError) as error:
        parser.exit(2, f"Unable to inspect presentation: {error}\n")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return int(bool(report.get("possible_losses")))


if __name__ == "__main__":
    raise SystemExit(main())
