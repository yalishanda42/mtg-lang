# Vendored data — Ivanchev spelling converter

These word lists come from **Peshowe/converter-web-app** by Petar Nedelev (with Todor Chervenkov and
Pavel Mihaylov), the engine behind <https://pravopis.osvedomitel.bg/>, used under the MIT License
(`LICENSE.md` in this directory).

- Source: <https://github.com/Peshowe/converter-web-app>, commit
  `d4db8e961d57b8880744b820388fbe1035ab2e1e`, directory `converter/static/converter/word_lists/`
- Downloaded: 2026-11-25. Only change: UTF-8 byte-order marks removed.
- Ported logic: `converter/converter.py` and `converter/process_vocabs.py` → `mtglang/ortho/ivanchev.py`.

Not vendored, on purpose:

- `most_freq.txt` (21 MB) — only a speed cache of pre-converted frequent words.
- The BERT part-of-speech weights — only used to tell verbs from nouns among `-те` homographs; without them
  the upstream converter (and this port) takes the non-verb reading, so a few such words need overrides.

The upstream paired test texts are in `tests/fixtures/ortho/` (same commit).
