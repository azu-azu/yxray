# Deferred Items — Phase 15

## Out-of-Scope Pre-existing Issues

### test_port_probe.py::test_find_available_port_returns_7433

- **Discovered during:** Plan 15-05, Task 1 (test suite run)
- **Scope:** Pre-existing — created in Phase 10-01 (commit e79db82), not Phase 15
- **Issue:** `test_find_available_port_returns_7433` fails when port 7433 is already
  bound on the development machine (e.g., a running app instance)
- **Behavior:** The test asserts `port == 7433` but gets `7434` because the app
  instance occupying 7433 causes `find_available_port()` to skip to the next port.
  The function itself is working correctly.
- **Fix direction (deferred):** Either: (a) pre-bind a mock socket in the test
  to ensure 7433 is free before calling `find_available_port()`, or (b) accept
  that this test is environment-sensitive and mark it `@pytest.mark.skipif`
  when 7433 is known-occupied.
- **Impact:** Zero — all 18 Phase 15 tests and 170 of 171 total tests pass.
  The failing test is unrelated to any Phase 15 functionality.
