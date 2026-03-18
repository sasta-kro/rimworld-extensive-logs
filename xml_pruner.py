import xml.etree.ElementTree as ET
import sys

def prune_xml_tree(element, max_repeats=2):
    """
    Recursively strips out text content and truncates repeating XML tags.
    """
    # Clear out the actual data/text to save token space
    if element.text and element.text.strip():
        element.text = "..."

    tag_counts = {}
    children_to_remove = []

    # Iterate over a copy of the children list
    for child in list(element):
        tag = child.tag
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # If we hit the limit, insert a dummy tag to show truncation
        if tag_counts[tag] == max_repeats + 1:
            marker = ET.Element(f"---MORE_{tag}_NODES_TRUNCATED---")
            # Insert the marker exactly where the truncation begins
            element.insert(list(element).index(child), marker)
            children_to_remove.append(child)

        # If we are past the limit, just mark for removal
        elif tag_counts[tag] > max_repeats + 1:
            children_to_remove.append(child)

        # Otherwise, keep it and recurse deeper into the tree
        else:
            prune_xml_tree(child, max_repeats)

    # Remove all the excess repeating children
    for child in children_to_remove:
        element.remove(child)

def generate_skeleton(input_xml_path, output_xml_path):
    print(f"Loading heavy XML: {input_xml_path}...")
    tree = ET.parse(input_xml_path)
    root = tree.getroot()

    print("Pruning tree structure...")
    prune_xml_tree(root, max_repeats=2)  # Adjust this number to see more/fewer repetitions

    print(f"Saving compressed skeleton to: {output_xml_path}...")
    tree.write(output_xml_path, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    # Example usage:
    # python xml_skeleton.py world_000_save.xml compressed_skeleton.xml
    input_file = "_test_files/Dilunasol p4.9 progress/world/000_save"  # Replace with your extracted save file path
    output_file = "_test_outputs/compressed_skeleton.xml"
    generate_skeleton(input_file, output_file)