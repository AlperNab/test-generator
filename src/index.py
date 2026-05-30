#!/usr/bin/env python3
"""
test-generator — function or module → complete test suite
Unit tests, integration tests, edge cases, mocks — pytest, Jest, RSpec, Go test
"""
import anthropic, json, re, sys
from pathlib import Path

SYSTEM = """You are a senior software engineer who writes tests that actually catch bugs.
Generate a comprehensive test suite for this code.

Rules:
- Test behavior, not implementation
- Cover: happy path, edge cases, error cases, boundary values
- Use realistic test data (not "test" or "foo")
- Each test should have exactly one reason to fail
- Mock external dependencies appropriately
- Include parameterized tests where the pattern repeats

Return ONLY valid JSON — no markdown, no explanation.

{
  "language": "python|typescript|javascript|ruby|go|java|other",
  "framework": "pytest|jest|rspec|go_test|junit|other",
  "source_function": "name of main function/module being tested",
  "coverage_analysis": {
    "branches_identified": number,
    "test_coverage_pct": number,
    "uncoverable": ["things that can't be unit tested"]
  },
  "test_file": "complete test file content ready to run",
  "test_cases": [
    {
      "name": "test_function_name_or_it_description",
      "type": "unit|integration|edge_case|error|performance|parametrized",
      "description": "what this test verifies",
      "scenario": "the specific scenario being tested",
      "mocks_needed": ["list of things to mock"],
      "expected_outcome": "what should happen"
    }
  ],
  "mocking_strategy": "description of what to mock and why",
  "fixtures": ["test fixtures or factories needed"],
  "setup_instructions": "how to run these tests (pip install|npm install|etc.)",
  "ci_snippet": "GitHub Actions or CI config snippet to run these tests",
  "coverage_command": "command to check coverage",
  "confidence": 0.0
}"""

def generate(code_source: str, framework: str = "auto", extra_context: str = "") -> dict:
    client = anthropic.Anthropic()
    path = Path(code_source)
    code = path.read_text(encoding="utf-8",errors="replace")[:30000] if path.exists() else code_source[:30000]

    # Detect language from file extension
    lang_hint = ""
    if path.exists():
        ext_map = {".py":"Python/pytest",".ts":"TypeScript/Jest",".js":"JavaScript/Jest",".rb":"Ruby/RSpec",".go":"Go/testing"}
        lang_hint = ext_map.get(path.suffix.lower(),"")

    context_parts = [
        f"Language/Framework hint: {lang_hint}" if lang_hint else "",
        f"Preferred framework: {framework}" if framework != "auto" else "",
        f"Context: {extra_context}" if extra_context else "",
        f"\nCode to test:\n{code}"
    ]
    prompt = "\n".join(p for p in context_parts if p)

    resp = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=4096, system=SYSTEM,
        messages=[{"role":"user","content":f"Generate tests for:\n\n{prompt}"}]
    )
    raw = re.sub(r'^```(?:json)?\s*','',resp.content[0].text.strip(),flags=re.MULTILINE)
    raw = re.sub(r'\s*```$','',raw,flags=re.MULTILINE)
    return json.loads(raw)

def print_summary(r: dict):
    cases = r.get("test_cases",[])
    cov = r.get("coverage_analysis",{})
    print(f"\n{'═'*60}")
    print(f"  TEST GENERATOR — {r.get('source_function','?')}")
    print(f"  {r.get('language','?')} | {r.get('framework','?')} | {len(cases)} tests | {cov.get('test_coverage_pct',0)}% coverage")
    print(f"{'═'*60}")

    TYPE_ICON = {"unit":"🔵","integration":"🟡","edge_case":"🟠","error":"🔴","performance":"⚡","parametrized":"🔄"}
    for case in cases:
        icon = TYPE_ICON.get(case.get("type","unit"),"•")
        print(f"\n  {icon} {case.get('name','')}")
        print(f"     {case.get('description','')}")
        if case.get("mocks_needed"): print(f"     Mocks: {', '.join(case['mocks_needed'][:3])}")

    print(f"\n  Setup: {r.get('setup_instructions','')}")
    print(f"  Coverage cmd: {r.get('coverage_command','')}")
    uncov = cov.get("uncoverable",[])
    if uncov: print(f"  Not coverable: {', '.join(uncov[:3])}")
    print(f"\n  ✅ Full test file included in --json output")
    print(f"  Confidence: {int(r.get('confidence',0)*100)}%")
    print(f"{'═'*60}\n")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Generate complete test suite for any function or module")
    p.add_argument("source", help="Source file or raw code")
    p.add_argument("--framework","-f",default="auto",help="pytest|jest|rspec|go_test")
    p.add_argument("--context","-c",default="",help="Extra context about the module")
    p.add_argument("--output","-o",help="Save test file to path")
    p.add_argument("--json",action="store_true")
    a = p.parse_args()
    r = generate(a.source, a.framework, a.context)
    if a.output:
        Path(a.output).write_text(r.get("test_file",""), encoding="utf-8")
        print(f"Test file saved to {a.output}")
    if a.json: print(json.dumps(r,indent=2,ensure_ascii=False))
    else: print_summary(r)
