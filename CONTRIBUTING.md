# Contributing to argument-map

Thanks for helping make paper reasoning easier to inspect.

## Development loop

1. Fork the repository and create a focused branch.
2. Make the smallest change that improves the builder, renderer, documentation, or examples.
3. Run the release gate:

   ```bash
   python3 tests/run_tests.py
   python3 scripts/release_check.py
   ```

4. Open a pull request with a short explanation and the commands you ran.

## Good first contributions

- Add a paper graph to `examples/`.
- Improve source verification for a real PDF layout.
- Add a renderer interaction with a keyboard accessible fallback.
- Improve the English documentation or add a translated guide.

Please keep generated HTML self-contained and avoid network-loaded runtime dependencies.
