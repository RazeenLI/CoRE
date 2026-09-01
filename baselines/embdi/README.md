# EmbDI baseline

This baseline preserves EmbDI's heterogeneous graph, random-walk corpus,
Skip-gram training, and cosine-based schema matching. The obsolete Gensim
backend is replaced with the same negative-sampling Skip-gram objective in the
project's existing PyTorch runtime.

For every case, the graph contains only the current existing RDB and incoming
table. Graph construction, walk generation, training, matching, and evolution
rule conversion are all included in end-to-end latency. This is an adapted
implementation; the original EmbDI system does not emit RDB evolution actions.

The current configuration uses CUDA. Select the physical GPU with
`CUDA_VISIBLE_DEVICES`; inside the process EmbDI uses the first visible device.

Original implementation: https://github.com/rcap107/embdi (Apache-2.0).
