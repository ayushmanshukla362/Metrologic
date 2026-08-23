from backend.ai_extractor import OCRBlock
from backend.vision_evidence import (
    VISION_OCR_COVERAGE_THRESHOLD,
    VISION_OCR_IOU_THRESHOLD,
    VISION_OCR_OVERLAP_THRESHOLD,
    calculate_spatial_metrics,
    convert_ocr_bbox_to_native,
    convert_vision_bbox_to_native,
    map_vision_evidence,
)
from backend.vision_extractor import VisionExtraction


def _vision_result(**overrides):
    payload = {
        "commodity_name": {"value": None, "raw_source": None, "bbox": None},
        "net_quantity": {
            "value": None,
            "unit": None,
            "raw_source": None,
            "bbox": None,
        },
        "mfg_date": {"value": None, "raw_source": None, "bbox": None},
        "mrp": {"value": None, "unit": None, "raw_source": None, "bbox": None},
        "manufacturer": {"value": None, "raw_source": None, "bbox": None},
    }
    payload.update(overrides)
    return VisionExtraction.model_validate(payload)


def _field(value=50, bbox=None, raw_source="MRP Rs. 50"):
    return {
        "value": value,
        "unit": "INR",
        "raw_source": raw_source,
        "bbox": bbox,
    }


def _ocr_block(block_id, bbox):
    x1, y1, x2, y2 = bbox
    return OCRBlock(
        block_id=block_id,
        text="MRP",
        bbox=[x1, y1, x2 - x1, y2 - y1],
        ocr_confidence=95.0,
        normalized_x1=0.0,
        normalized_y1=0.0,
        normalized_x2=1.0,
        normalized_y2=1.0,
    )


def _raw_ocr_block(
    block_id, bbox, width=1200, height=1600, text="evidence"
):
    x, y, block_width, block_height = bbox
    return OCRBlock(
        block_id=block_id,
        text=text,
        bbox=bbox,
        ocr_confidence=95.0,
        normalized_x1=x / width,
        normalized_y1=y / height,
        normalized_x2=(x + block_width) / width,
        normalized_y2=(y + block_height) / height,
    )


def _map(result, blocks, image_id="img_front", width=1000, height=1000):
    return map_vision_evidence(result, blocks, image_id, width, height)


def test_one_vision_bbox_matches_one_ocr_block():
    result = _vision_result(mrp=_field(bbox=[10, 10, 50, 30]))
    blocks = [_ocr_block("img_front:b001", [10, 10, 50, 30])]

    mapped = _map(result, blocks)

    assert mapped["mrp"]["source_block_ids"] == ["img_front:b001"]
    assert mapped["mrp"]["value"] == 50
    assert mapped["mrp"]["bbox"] == [10, 10, 50, 30]


def test_one_vision_bbox_matches_multiple_ocr_blocks():
    result = _vision_result(mrp=_field(bbox=[10, 10, 110, 30]))
    blocks = [
        _ocr_block("img_front:b001", [10, 10, 50, 30]),
        _ocr_block("img_front:b002", [60, 10, 110, 30]),
    ]

    mapped = _map(result, blocks)

    assert mapped["mrp"]["source_block_ids"] == [
        "img_front:b001",
        "img_front:b002",
    ]


def test_no_overlap_returns_empty_evidence():
    result = _vision_result(mrp=_field(bbox=[10, 10, 50, 30]))
    blocks = [_ocr_block("img_front:b001", [100, 100, 140, 120])]

    mapped = _map(result, blocks)

    assert mapped["mrp"]["source_block_ids"] == []


def test_below_threshold_overlap_returns_empty_evidence():
    result = _vision_result(mrp=_field(bbox=[0, 0, 10, 10]))
    blocks = [_ocr_block("img_front:b001", [8, 8, 28, 28])]

    mapped = _map(result, blocks)

    assert mapped["mrp"]["source_block_ids"] == []


def test_overlap_at_named_threshold_is_included():
    result = _vision_result(mrp=_field(bbox=[0, 0, 25, 100]))
    blocks = [_ocr_block("img_front:b001", [0, 0, 100, 100])]

    mapped = _map(result, blocks)

    assert VISION_OCR_OVERLAP_THRESHOLD == 0.25
    assert mapped["mrp"]["source_block_ids"] == ["img_front:b001"]


def test_null_vision_bbox_returns_empty_evidence():
    result = _vision_result(mrp=_field(bbox=None))
    blocks = [_ocr_block("img_front:b001", [0, 0, 100, 100])]

    mapped = _map(result, blocks)

    assert mapped["mrp"]["source_block_ids"] == []


def test_null_field_value_returns_empty_evidence():
    result = _vision_result(mrp=_field(value=None, bbox=[0, 0, 100, 100]))
    blocks = [_ocr_block("img_front:b001", [0, 0, 100, 100])]

    mapped = _map(result, blocks)

    assert mapped["mrp"]["source_block_ids"] == []


def test_wrong_image_ocr_block_is_ignored():
    result = _vision_result(mrp=_field(bbox=[0, 0, 100, 100]))
    blocks = [_ocr_block("img_back:b001", [0, 0, 100, 100])]

    mapped = _map(result, blocks)

    assert mapped["mrp"]["source_block_ids"] == []


def test_source_block_ids_have_deterministic_spatial_ordering():
    result = _vision_result(mrp=_field(bbox=[0, 0, 100, 100]))
    blocks = [
        _ocr_block("img_front:b002", [50, 20, 80, 40]),
        _ocr_block("img_front:b003", [10, 50, 40, 70]),
        _ocr_block("img_front:b001", [10, 20, 40, 40]),
    ]

    first = _map(result, blocks)
    second = _map(result, list(reversed(blocks)))

    expected = ["img_front:b001", "img_front:b002", "img_front:b003"]
    assert first["mrp"]["source_block_ids"] == expected
    assert second["mrp"]["source_block_ids"] == expected


def test_known_mfg_date_bbox_converts_to_native_pixels():
    assert convert_vision_bbox_to_native(
        [386, 880, 721, 906], 1200, 1600
    ) == [463, 1408, 865, 1450]


def test_known_mrp_bbox_converts_to_native_pixels():
    assert convert_vision_bbox_to_native(
        [394, 932, 579, 954], 1200, 1600
    ) == [473, 1491, 695, 1526]


def test_known_manufacturer_bbox_converts_to_native_pixels():
    assert convert_vision_bbox_to_native(
        [283, 163, 892, 368], 1200, 1600
    ) == [340, 261, 1070, 589]


def test_ocr_bbox_converts_from_origin_and_size_to_native_endpoints():
    assert convert_ocr_bbox_to_native([10, 20, 30, 40]) == [10, 20, 40, 60]


def test_ocr_bbox_zero_width_and_height_is_a_zero_area_rectangle():
    assert convert_ocr_bbox_to_native([10, 20, 0, 0]) == [10, 20, 10, 20]


def test_ocr_bbox_negative_width_or_height_is_rejected():
    assert convert_ocr_bbox_to_native([10, 20, -1, 40]) is None
    assert convert_ocr_bbox_to_native([10, 20, 30, -1]) is None


def test_mrp_ocr_bbox_converts_to_expected_native_rectangle():
    assert convert_ocr_bbox_to_native([475, 1453, 557, 66]) == [475, 1453, 1032, 1519]


def test_known_mrp_spatial_metrics_pass_two_sided_thresholds():
    vision_bbox = convert_vision_bbox_to_native([394, 932, 579, 954], 1200, 1600)
    ocr_bbox = convert_ocr_bbox_to_native([475, 1453, 557, 66])

    metrics = calculate_spatial_metrics(vision_bbox, ocr_bbox)

    assert metrics["intersection_area"] == 6160.0
    assert metrics["ocr_coverage"] == 6160 / 36762
    assert metrics["vision_coverage"] == 6160 / 7770
    assert metrics["iou"] == 6160 / 38372
    assert metrics["ocr_coverage"] >= VISION_OCR_COVERAGE_THRESHOLD
    assert metrics["iou"] >= VISION_OCR_IOU_THRESHOLD


def test_mrp_candidate_maps_with_two_sided_spatial_acceptance():
    result = _vision_result(mrp=_field(value=449, bbox=[394, 932, 579, 954]))
    blocks = [_raw_ocr_block("test:b138", [475, 1453, 557, 66])]

    mapped = map_vision_evidence(result, blocks, "test", 1200, 1600)

    assert mapped["mrp"]["source_block_ids"] == ["test:b138"]


def test_small_ocr_block_inside_large_manufacturer_box_is_rejected():
    result = _vision_result(
        manufacturer={
            "value": "Spectacle Foods",
            "raw_source": "Manufactured By: Spectacle Foods",
            "bbox": [281, 160, 892, 368],
        }
    )
    blocks = [_raw_ocr_block("test:small", [500, 400, 30, 20])]

    mapped = map_vision_evidence(result, blocks, "test", 1200, 1600)

    assert mapped["manufacturer"]["source_block_ids"] == []


def test_complete_manufacturer_declaration_block_is_accepted():
    result = _vision_result(
        manufacturer={
            "value": "Spectacle Foods",
            "raw_source": "Manufactured By: Spectacle Foods",
            "bbox": [281, 160, 892, 368],
        }
    )
    blocks = [_raw_ocr_block("test:b999", [198, 455, 610, 47])]

    mapped = map_vision_evidence(result, blocks, "test", 1200, 1600)

    assert mapped["manufacturer"]["source_block_ids"] == [
        "test:b999"
    ]


def test_true_manufacturer_word_block_is_accepted():
    result = _vision_result(
        manufacturer={
            "value": "Spectacle Foods",
            "raw_source": "Manufactured By: Spectacle Foods",
            "bbox": [281, 160, 892, 368],
        }
    )
    blocks = [_raw_ocr_block("test:b037", [497, 455, 180, 43])]

    mapped = map_vision_evidence(result, blocks, "test", 1200, 1600)

    assert mapped["manufacturer"]["source_block_ids"] == ["test:b037"]


def test_converted_mrp_vision_bbox_overlaps_converted_ocr_block():
    result = _vision_result(
        mrp=_field(value=449, bbox=[386, 919, 593, 957])
    )
    blocks = [_ocr_block("test:b001", [475, 1453, 1032, 1519])]

    mapped = map_vision_evidence(result, blocks, "test", 1200, 1600)

    assert mapped["mrp"]["source_block_ids"] == ["test:b001"]


def test_original_ocr_bbox_is_not_mutated_by_mapping():
    raw_bbox = [475, 1453, 557, 66]
    block = OCRBlock(
        block_id="test:b001",
        text="MRP",
        bbox=raw_bbox.copy(),
        ocr_confidence=95.0,
        normalized_x1=475 / 1200,
        normalized_y1=1453 / 1600,
        normalized_x2=(475 + 557) / 1200,
        normalized_y2=(1453 + 66) / 1600,
    )
    result = _vision_result(mrp=_field(value=449, bbox=[386, 919, 593, 957]))

    mapped = map_vision_evidence(result, [block], "test", 1200, 1600)

    assert block.bbox == raw_bbox
    assert mapped["mrp"]["source_block_ids"] == ["test:b001"]


def test_all_known_boxes_map_to_corresponding_current_image_ocr_ids():
    result = _vision_result(
        mfg_date={
            "value": "23/05/2025",
            "raw_source": "Mfg. Date: 23/05/2025",
            "bbox": [386, 880, 721, 906],
        },
        mrp={
            "value": 449,
            "unit": "INR",
            "raw_source": "MRP 449",
            "bbox": [394, 932, 579, 954],
        },
        manufacturer={
            "value": "Spectacle Foods",
            "raw_source": "Manufactured By: Spectacle Foods",
            "bbox": [283, 163, 892, 368],
        },
    )
    blocks = [
        _ocr_block("test:b001", [463, 1408, 865, 1450]),
        _ocr_block("test:b002", [473, 1491, 695, 1526]),
        _ocr_block("test:b003", [340, 261, 1070, 589]),
    ]

    mapped = map_vision_evidence(result, blocks, "test", 1200, 1600)

    assert mapped["mfg_date"]["source_block_ids"] == ["test:b001"]
    assert mapped["mrp"]["source_block_ids"] == ["test:b002"]
    assert mapped["manufacturer"]["source_block_ids"] == ["test:b003"]


def test_converted_known_bbox_maps_to_native_ocr_block():
    result = _vision_result(mfg_date={
        "value": "23/05/2025",
        "raw_source": "Mfg. Date: 23/05/2025",
        "bbox": [386, 880, 721, 906],
    })
    blocks = [_ocr_block("test:b001", [463, 1408, 865, 1450])]

    mapped = map_vision_evidence(result, blocks, "test", 1200, 1600)

    assert mapped["mfg_date"]["source_block_ids"] == ["test:b001"]
    assert mapped["mfg_date"]["bbox"] == [386, 880, 721, 906]


def test_malformed_vision_bbox_is_rejected_without_reordering():
    result = {
        "mrp": _field(bbox=[902, 395, 579, 845]),
    }
    blocks = [_ocr_block("img_front:b001", [600, 600, 100, 100])]

    mapped = map_vision_evidence(result, blocks, "img_front", 1200, 1600)

    assert mapped["mrp"]["source_block_ids"] == []
    assert mapped["mrp"]["bbox"] == [902, 395, 579, 845]


def test_converted_bbox_keeps_wrong_image_ids_excluded():
    result = _vision_result(mrp=_field(bbox=[394, 932, 579, 954]))
    blocks = [
        _ocr_block("other_image:b001", [473, 1491, 695, 1526]),
        _ocr_block("img_front:b002", [10, 10, 20, 20]),
    ]

    mapped = map_vision_evidence(result, blocks, "img_front", 1200, 1600)

    assert mapped["mrp"]["source_block_ids"] == []


def test_net_quantity_borderline_spatial_match_uses_exact_text_corroboration():
    result = _vision_result(
        net_quantity={
            "value": 125,
            "unit": "g",
            "raw_source": "125 g",
            "bbox": [271, 307, 305, 344],
        }
    )
    blocks = [
        _raw_ocr_block(
            "tests:b043",
            [436, 268, 90, 41],
            width=1528,
            height=993,
            text="125g",
        )
    ]

    mapped = map_vision_evidence(result, blocks, "tests", 1528, 993)

    assert mapped["net_quantity"]["source_block_ids"] == ["tests:b043"]


def test_unrelated_numeric_ocr_block_is_not_secondary_evidence():
    result = _vision_result(
        net_quantity={
            "value": 125,
            "unit": "g",
            "raw_source": "125 g",
            "bbox": [271, 307, 305, 344],
        }
    )
    blocks = [
        _raw_ocr_block(
            "tests:b043",
            [436, 268, 90, 41],
            width=1528,
            height=993,
            text="987654",
        )
    ]

    mapped = map_vision_evidence(result, blocks, "tests", 1528, 993)

    assert mapped["net_quantity"]["source_block_ids"] == []


def test_mrp_decimal_text_matches_integer_vision_value():
    result = _vision_result(
        mrp={
            "value": 449,
            "unit": "INR",
            "raw_source": "MRP 449",
            "bbox": [394, 932, 579, 954],
        }
    )
    blocks = [_raw_ocr_block("test:b138", [475, 1453, 557, 66], text="449.00")]

    mapped = map_vision_evidence(result, blocks, "test", 1200, 1600)

    assert mapped["mrp"]["source_block_ids"] == ["test:b138"]


def test_date_text_is_compared_by_normalized_date_components():
    result = _vision_result(
        mfg_date={
            "value": "23/05/2025",
            "raw_source": "Mfg. Date: 23/05/2025",
            "bbox": [394, 932, 579, 954],
        }
    )
    blocks = [_raw_ocr_block("test:b138", [475, 1453, 557, 66], text="23-05-2025")]

    mapped = map_vision_evidence(result, blocks, "test", 1200, 1600)

    assert mapped["mfg_date"]["source_block_ids"] == ["test:b138"]


def test_borderline_wrong_image_candidate_is_rejected_before_corroboration():
    result = _vision_result(
        net_quantity={
            "value": 125,
            "unit": "g",
            "raw_source": "125 g",
            "bbox": [271, 307, 305, 344],
        }
    )
    blocks = [
        _raw_ocr_block(
            "other:b043",
            [436, 268, 90, 41],
            width=1528,
            height=993,
            text="125g",
        )
    ]

    mapped = map_vision_evidence(result, blocks, "tests", 1528, 993)

    assert mapped["net_quantity"]["source_block_ids"] == []
