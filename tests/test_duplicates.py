from flashcard_app.duplicates import find_duplicate_groups, first_duplicate, is_near_duplicate


def test_exact_and_near_duplicates():
    assert is_near_duplicate("ATP", "atp")
    assert not is_near_duplicate("Cat", "Car")
    items = [
        (1, "Mitochondria are the powerhouse of the cell"),
        (2, "Mitochondria are the powerhouse of a cell"),
        (3, "Photosynthesis uses sunlight"),
        (4, "photosynthesis uses sunlight"),
    ]
    groups = find_duplicate_groups(items)
    assert sorted(sorted(group) for group in groups) == [[1, 2], [3, 4]]
    assert first_duplicate("ATP", [(1, "atp")]) == "atp"
    assert first_duplicate("Cat", [(1, "Car")]) is None
