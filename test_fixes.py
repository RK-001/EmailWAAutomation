#!/usr/bin/env python3
"""
test_fixes.py - Verify all 3 fixes applied correctly
"""
import sys
import json
import os

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

def test_profile_params():
    """Test 5: Verify profiles define usable WhatsApp body params"""
    print("\n" + "="*60)
    print("TEST 5: Profile WhatsApp Template Params")
    print("="*60)

    from core.batch_runner import _build_whatsapp_template_params
    
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    
    profiles = cfg.get("profiles", {})
    
    for pname, pdata in profiles.items():
        wa_params = pdata.get("wa_template_params", [])
        
        if not isinstance(wa_params, list) or not wa_params:
            print(f"✗ ERROR: {pname} has invalid wa_template_params: {wa_params}")
            return False
        
        if "drive_link" not in wa_params:
            print(f"✗ ERROR: {pname} missing 'drive_link' in wa_template_params")
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

def main():
    tests = [
        ("Default Config Template", test_default_config),
        ("Validate Method", test_validate_method),
        ("Workflow Tab Comment", test_workflow_tab_comment),
        ("config.json Structure", test_config_json),
        ("Profile WhatsApp Params", test_profile_params),
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
