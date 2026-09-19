# Kronos Architecture Compatibility Report

## 1. Components Reusability
The original `Kronos` ecosystem consists of two separate models:
1. **`KronosTokenizer`**: An encoder-decoder using `BinarySphericalQuantizer` to compress continuous OHLCV data into discrete binary tokens (`s1_bits`, `s2_bits`).
2. **`Kronos` (Transformer)**: An autoregressive model that learns the transition probabilities of these discrete tokens.

**Direct Reuse**: 
- The `KronosTokenizer` can and should be reused **completely unmodified** and **frozen**. Its job is to encode/decode the 6 canonical market variables (OHLCV + amount). We do not need it to reconstruct auxiliary technical indicators (like RSI or SMA distances) since we only care about predicting future price/volume.
- The `Kronos` Transformer's entire backbone (TransformerBlocks, RMSNorm, DualHead, HierarchicalEmbedding) can be transferred and reused.

## 2. Modifications for Extra Features
If we modify the `KronosTokenizer` to accept `d_in=32` instead of `6`:
- The Tokenizer's `embed` (`6 -> d_model`) and `head` (`d_model -> 6`) linear layers would require shape changes, breaking pretrained weights.
- More importantly, forcing the tokenizer to compress 32 features into the same bit-budget would fundamentally alter the semantic meaning of every token in the vocabulary.
- Consequently, the `Kronos` Transformer's pretrained weights would become completely invalid because the "language" of the tokens would have changed. Retraining from scratch would be required.

## 3. Is `d_in=32` Compatible with Pretrained Weights?
No. Changing `d_in=32` at the tokenizer level destroys the semantic validity of the pretrained codebook and transformer.

## 4. Proposed Feature-Aware Architecture (Native Fusion)
Instead of modifying the Tokenizer, we can inject auxiliary features directly into the **Transformer's latent space**.

**Design**:
1. Input the 6 canonical OHLCV variables into the frozen `KronosTokenizer` to get target tokens.
2. Embed the tokens using the pretrained `HierarchicalEmbedding` ($X_{tok} \in \mathbb{R}^{d\_model}$).
3. Pass the $N$ auxiliary features through a newly initialized `aux_encoder` ($N \rightarrow d\_model$).
4. **Zero-Initialize** the final layer of the `aux_encoder` so that at epoch 0, $X_{aux} = 0$.
5. Combine representations: $X_{input} = X_{tok} + X_{time} + X_{aux}$.
6. Pass $X_{input}$ through the pretrained Transformer blocks.

## 5. Weight Transferability
Under this Native Fusion design:
- **100% of the pretrained Tokenizer weights** are transferred and frozen.
- **100% of the pretrained Transformer weights** are transferred. 
- Only the new `aux_encoder` (e.g., a lightweight MLP) needs initialization.
- Because `aux_encoder` is zero-initialized, the initial forward pass is mathematically identical to the original pretrained model. This prevents catastrophic forgetting and allows the model to gently learn to attend to the new features.

## 6. Should Fine-Tuning the Original 6-Feature Representation Be Tested First?
Yes (Experiment 1). Before introducing auxiliary features, we must establish a fine-tuning baseline. If the frozen model cannot even be successfully fine-tuned on the native 6 features (e.g., due to immediate overfitting on the new dataset), then adding dozens of auxiliary features will only exacerbate the overfitting. We must prove the transformer can still learn robustly before we expand its input space.
