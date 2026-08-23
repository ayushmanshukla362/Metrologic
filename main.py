from schemas import PackageData, ExtractedField
from rules import check_mrp

# Test 1: Fake Data (Sahi MRP)
test_data_good = PackageData(
    session_id="test_001",
    mrp=ExtractedField(field_key="mrp", value="120", unit="INR", confidence=0.95)
)

# Test 2: Fake Data (Dhundhla/Blur MRP)
test_data_blur = PackageData(
    session_id="test_002",
    mrp=ExtractedField(field_key="mrp", value="120", unit="INR", confidence=0.60)
)

print("--- TEST 1 (Good Image) ---")
result1 = check_mrp(test_data_good)
print(f"Status: {result1.status} | Reason: {result1.reason}")

print("\n--- TEST 2 (Blurry Image) ---")
result2 = check_mrp(test_data_blur)
print(f"Status: {result2.status} | Reason: {result2.reason}")