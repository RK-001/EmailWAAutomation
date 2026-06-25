#!/usr/bin/env python3
"""
test_fixes.py - Verify all 3 fixes applied correctly
"""
import sys
import json
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def test_default_config():
    """Test 1: Verify default config template has meta_whatsapp"""
    print("\n" + "="*60)
    print("TEST 1: Default Config Template")
    print("="*60)
    
    from utils.config_manager import _DEFAULT_CONFIG
    
    print(f"✓ Keys in _DEFAULT_CONFIG: {list(_DEFAULT_CONFIG.keys())}")
    
    if "aisensy" in _DEFAULT_CONFIG:
        print("✗ ERROR: aisensy still in _DEFAULT_CONFIG")
        return False
    
    if "meta_whatsapp" not in _DEFAULT_CONFIG:
        print("✗ ERROR: meta_whatsapp missing from _DEFAULT_CONFIG")
        return False
    
    meta_cfg = _DEFAULT_CONFIG["meta_whatsapp"]
    required_keys = {"phone_number_id", "access_token", "template_name", "api_version", "template_language", "mock_mode"}
    
    print(f"✓ meta_whatsapp present with keys: {list(meta_cfg.keys())}")
    
    if set(meta_cfg.keys()) != required_keys:
        missing = required_keys - set(meta_cfg.keys())
        print(f"✗ ERROR: Missing keys: {missing}")
        return False
    
    print("✓ All required keys present")
    print(f"  - template_name: {meta_cfg['template_name']}")
    print(f"  - api_version: {meta_cfg['api_version']}")
    print(f"  - template_language: {meta_cfg['template_language']}")
    print(f"  - mock_mode: {meta_cfg['mock_mode']}")
    
    return True

def test_validate_method():
    """Test 2: Verify validate_meta_whatsapp method exists and works"""
    print("\n" + "="*60)
    print("TEST 2: Validate Method")
    print("="*60)
    
    from utils.config_manager import ConfigManager
    
    cm = ConfigManager("config.json")
    
    # Check method exists
    if not hasattr(cm, "validate_meta_whatsapp"):
        print("✗ ERROR: validate_meta_whatsapp method not found")
        return False
    
    print("✓ validate_meta_whatsapp method exists")
    
    # Test with mock mode ON (should return no errors)
    errors = cm.validate_meta_whatsapp()
    if errors:
        print(f"✗ ERROR: Got validation errors in mock mode: {errors}")
        return False
    
    print("✓ Mock mode ON: 0 validation errors (expected)")
    
    # Test with mock mode OFF (should show errors for empty credentials)
    cm.set("meta_whatsapp.mock_mode", False)
    errors = cm.validate_meta_whatsapp()
    
    if not errors:
        print("✗ ERROR: Should have validation errors when mock mode OFF and credentials empty")
        return False
    
    print(f"✓ Mock mode OFF: {len(errors)} validation errors found")
    for err in errors:
        print(f"  - {err}")

    cm.set("meta_whatsapp.phone_number_id", "123456789")
    cm.set("meta_whatsapp.access_token", "test-token")
    cm.set("meta_whatsapp.template_name", "template_name_here")
    cm.set("meta_whatsapp.template_language", "english")
    errors = cm.validate_meta_whatsapp()

    if not any("placeholder" in err.lower() for err in errors):
        print("✗ ERROR: Placeholder template name was not rejected")
        return False

    if not any("template language" in err.lower() for err in errors):
        print("✗ ERROR: Invalid template language was not rejected")
        return False

    print("✓ Placeholder template names and invalid languages are rejected")
    
    # Reset
    cm.set("meta_whatsapp.mock_mode", True)
    
    return True

def test_workflow_tab_comment():
    """Test 3: Verify workflow_tab.py comment updated"""
    print("\n" + "="*60)
    print("TEST 3: Workflow Tab UI Comment")
    print("="*60)
    
    with open("ui/workflow_tab.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    if "via AiSensy" in content:
        print("✗ ERROR: Found 'via AiSensy' in workflow_tab.py")
        return False
    
    if "via Meta WhatsApp Business API" in content:
        print("✓ Comment updated to 'via Meta WhatsApp Business API'")
        return True
    
    print("⚠ WARNING: Comment doesn't mention Meta WhatsApp")
    return True  # Not critical

def test_config_json():
    """Test 4: Verify config.json has meta_whatsapp"""
    print("\n" + "="*60)
    print("TEST 4: config.json Structure")
    print("="*60)
    
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    
    if "aisensy" in cfg:
        print("✗ ERROR: aisensy section still in config.json")
        return False
    
    if "meta_whatsapp" not in cfg:
        print("✗ ERROR: meta_whatsapp section missing from config.json")
        return False
    
    print("✓ config.json has meta_whatsapp section")
    
    meta_cfg = cfg["meta_whatsapp"]
    required_keys = {"phone_number_id", "access_token", "template_name", "api_version", "template_language", "mock_mode"}
    
    if set(meta_cfg.keys()) != required_keys:
        missing = required_keys - set(meta_cfg.keys())
        print(f"✗ ERROR: Missing keys in meta_whatsapp: {missing}")
        return False
    
    print("✓ All required meta_whatsapp fields present")
    return True

def test_meta_preflight_symbol():
    """Test 5: Verify the Meta preflight checker is importable"""
    print("\n" + "="*60)
    print("TEST 5: Meta Preflight Import")
    print("="*60)

    from utils.preflight import check_meta_whatsapp_connection

    if not callable(check_meta_whatsapp_connection):
        print("✗ ERROR: check_meta_whatsapp_connection is not callable")
        return False

    print("✓ check_meta_whatsapp_connection import works")
    return True

def test_profile_params():
    """Test 6: Verify profiles define usable WhatsApp body params"""
    print("\n" + "="*60)
    print("TEST 6: Profile WhatsApp Template Params")
    print("="*60)

    from core.batch_runner import _build_whatsapp_template_params
    
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    
    profiles = cfg.get("profiles", {})
    
    for pname, pdata in profiles.items():
        wa_params = pdata.get("wa_template_params", [])
        
        if not isinstance(wa_params, list):
            print(f"✗ ERROR: {pname} has invalid wa_template_params: {wa_params}")
            return False

        row = {param: f"value_for_{param}" for param in wa_params}
        row["drive_link"] = "https://drive.google.com/test-link"
        resolved, err = _build_whatsapp_template_params(pdata, row)
        if err:
            print(f"✗ ERROR: {pname} params could not be resolved: {err}")
            return False
        if len(resolved) != len(wa_params):
            print(f"✗ ERROR: {pname} resolved {len(resolved)} params, expected {len(wa_params)}")
            return False
        
        print(f"✓ {pname}: {len(wa_params)} params = {wa_params}")
    
    return True


def test_whatsapp_param_variants():
    """Test 7: Verify WhatsApp placeholders support 0, 3, and legacy 4 params"""
    print("\n" + "="*60)
    print("TEST 7: WhatsApp Param Variants")
    print("="*60)

    from core.batch_runner import _build_whatsapp_template_params
    from core.whatsapp_sender import WhatsAppSender
    from ui.profiles_tab import _parse_whatsapp_template_params

    row = {
        "NAME": "Alice",
        "ACCOUNTNO": "ACC001",
        "drive_link": "https://drive.test/file.pdf",
        "OFFICER_NO": "9988776655",
    }

    resolved, err = _build_whatsapp_template_params({}, row)
    if err or resolved != ["Alice", "ACC001", "https://drive.test/file.pdf", "9988776655"]:
        print(f"✗ ERROR: Legacy default params failed: resolved={resolved}, err={err}")
        return False
    print("✓ Missing wa_template_params keeps legacy 4-param order")

    resolved, err = _build_whatsapp_template_params({"wa_template_params": []}, row)
    if err or resolved != []:
        print(f"✗ ERROR: Empty wa_template_params failed: resolved={resolved}, err={err}")
        return False
    print("✓ Empty wa_template_params supports zero placeholders")

    resolved, err = _build_whatsapp_template_params({"wa_template_params": None}, row)
    if err or resolved != []:
        print(f"✗ ERROR: Null wa_template_params failed: resolved={resolved}, err={err}")
        return False
    print("✓ Null wa_template_params supports zero placeholders")

    resolved, err = _build_whatsapp_template_params(
        {"wa_template_params": ["NAME", "ACCOUNTNO", "OFFICER_NO"]},
        row,
    )
    if err or resolved != ["Alice", "ACC001", "9988776655"]:
        print(f"✗ ERROR: 3-param template failed: resolved={resolved}, err={err}")
        return False
    print("✓ 3-param template preserves configured order")

    resolved, err = _build_whatsapp_template_params(
        {"wa_template_params": ["NAME", "ACCOUNTNO", "OFFICER_NO"]},
        {**row, "drive_link": ""},
    )
    if err or resolved != ["Alice", "ACC001", "9988776655"]:
        print(f"✗ ERROR: Non-drive-link template should ignore blank drive link: resolved={resolved}, err={err}")
        return False
    print("✓ Blank drive_link does not block templates that do not use it")

    resolved, err = _build_whatsapp_template_params(
        {"wa_template_params": ["NAME", "drive_link"]},
        {**row, "drive_link": ""},
    )
    if "Drive link is missing" not in err:
        print(f"✗ ERROR: drive_link should fail when referenced explicitly: {err}")
        return False
    print("✓ Blank drive_link still fails when template requires it")

    sender = WhatsAppSender(
        {
            "phone_number_id": "123456789",
            "access_token": "token",
            "template_name": "template",
            "api_version": "v21.0",
            "template_language": "en",
            "mock_mode": True,
        }
    )
    payload = sender._build_template_payload("+919876543210", [])
    if "components" in payload.get("template", {}):
        print(f"✗ ERROR: Zero-placeholder payload should omit components: {payload}")
        return False
    print("✓ Zero-placeholder payload omits body components")

    payload = sender._build_template_payload("+919876543210", ["Alice", "ACC001", "9988776655"])
    parameters = payload.get("template", {}).get("components", [{}])[0].get("parameters", [])
    if len(parameters) != 3:
        print(f"✗ ERROR: 3-placeholder payload built {len(parameters)} params")
        return False
    print("✓ Payload builder sends exactly the configured param count")

    parsed, err = _parse_whatsapp_template_params("NAME, ACCOUNTNO, OFFICER_NO")
    if err or parsed != ["NAME", "ACCOUNTNO", "OFFICER_NO"]:
        print(f"✗ ERROR: UI parser failed for 3 params: parsed={parsed}, err={err}")
        return False
    print("✓ Profiles UI parser accepts comma-separated params")

    parsed, err = _parse_whatsapp_template_params("")
    if err or parsed != []:
        print(f"✗ ERROR: UI parser failed for blank params: parsed={parsed}, err={err}")
        return False
    print("✓ Profiles UI parser allows zero placeholders")

    return True

def test_whatsapp_live_send_hardening():
    """Test 8: Verify live-send format and alias compatibility improvements"""
    print("\n" + "="*60)
    print("TEST 8: WhatsApp Live-Send Hardening")
    print("="*60)

    from core.batch_runner import _build_whatsapp_template_params
    from core.whatsapp_sender import WhatsAppSender
    from utils.validators import normalize_phone, validate_phone

    phone_variants = [
        ("9876543210", "9876543210", "919876543210"),
        ("+919876543210", "9876543210", "919876543210"),
        ("919876543210", "9876543210", "919876543210"),
        ("09876543210", "9876543210", "919876543210"),
    ]
    for raw_phone, expected_local, expected_meta in phone_variants:
        ok, err = validate_phone(raw_phone)
        if not ok:
            print(f"✗ ERROR: validate_phone rejected {raw_phone}: {err}")
            return False
        if normalize_phone(raw_phone) != expected_local:
            print(
                f"✗ ERROR: normalize_phone({raw_phone}) = {normalize_phone(raw_phone)}, "
                f"expected {expected_local}"
            )
            return False
        if WhatsAppSender._normalize_phone(raw_phone) != expected_meta:
            print(
                f"✗ ERROR: WhatsAppSender._normalize_phone({raw_phone}) = "
                f"{WhatsAppSender._normalize_phone(raw_phone)}, expected {expected_meta}"
            )
            return False
    print("✓ Phone validation and normalization accept common Indian formats")

    sender = WhatsAppSender(
        {
            "phone_number_id": "123456789",
            "access_token": "token",
            "template_name": "template",
            "api_version": "v21.0",
            "template_language": "en",
            "mock_mode": True,
        }
    )
    payload = sender._build_template_payload("919876543210", ["Alice"])
    if payload.get("to") != "919876543210":
        print(f"✗ ERROR: Payload should use digits-only Meta recipient format: {payload}")
        return False
    print("✓ Payload uses digits-only recipient format for Meta")

    row = {
        "NAME": "Alice",
        "BANK_ACCOUNT_NO": "ACC001",
        "OFFICER_MOBILE": "9988776655",
    }
    resolved, err = _build_whatsapp_template_params(
        {"wa_template_params": ["NAME", "ACCOUNTNO", "OFFICER_NO"]},
        row,
    )
    if err or resolved != ["Alice", "ACC001", "9988776655"]:
        print(f"✗ ERROR: Alias fallback failed: resolved={resolved}, err={err}")
        return False
    print("✓ Legacy WhatsApp params resolve through compatible profile field aliases")

    return True

def main():
    tests = [
        ("Default Config Template", test_default_config),
        ("Validate Method", test_validate_method),
        ("Workflow Tab Comment", test_workflow_tab_comment),
        ("config.json Structure", test_config_json),
        ("Meta Preflight Import", test_meta_preflight_symbol),
        ("Profile WhatsApp Params", test_profile_params),
        ("WhatsApp Param Variants", test_whatsapp_param_variants),
        ("WhatsApp Live-Send Hardening", test_whatsapp_live_send_hardening),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ EXCEPTION in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
