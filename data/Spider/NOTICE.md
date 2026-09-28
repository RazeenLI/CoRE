# Spider dataset attribution and license

The data artifacts in this directory are derived from **Spider 1.0**, created
by Tao Yu, Rui Zhang, Kai Yang, Michihiro Yasunaga, Dongxu Wang, Zifan Li,
James Ma, Irene Li, Qingning Yao, Shanelle Roman, Zilin Zhang, and Dragomir R.
Radev.

- Project and download page: <https://yale-lily.github.io/spider>
- Paper: *Spider: A Large-Scale Human-Labeled Dataset for Complex and
  Cross-Domain Semantic Parsing and Text-to-SQL Task*, EMNLP 2018
- Dataset license: [Creative Commons Attribution-ShareAlike 4.0
  International](https://creativecommons.org/licenses/by-sa/4.0/)

## Modifications

CoRE uses the source databases rather than Spider's natural-language questions
or gold SQL. The project imports database schemas and rows into a common
relational representation, normalizes data types, exports tables, constructs
semantic profiles, selects table/column/row subsets, and produces paired
existing, incoming, and expected benchmark states. Continuous-evolution
sequences under `data/continuous_benchmark/Spider/` are derived from the same
source.

The derived Spider data artifacts in `data/Spider/` and
`data/continuous_benchmark/Spider/` are made available under CC BY-SA 4.0.
Project-authored software, configuration, and documentation remain under the
repository's MIT license unless a file states otherwise.
