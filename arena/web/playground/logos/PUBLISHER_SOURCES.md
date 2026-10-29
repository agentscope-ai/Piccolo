# Publisher icons and model links

Verified on 2026-10-20. These icons identify the publisher of the listed
decision model. A backbone's publisher is not used as a substitute for the
model's publisher. Model scores, evaluation status, and model IDs are outside
the scope of this asset update.

## Decision Index reference

- Official hosted board: <https://huggingface.co/spaces/multimodalart/jev-decision-index>
- Official asset directory: <https://huggingface.co/spaces/multimodalart/jev-decision-index/tree/main/data/orgs>
- Historical metadata matching the local Public 0.3 results:
  <https://huggingface.co/spaces/multimodalart/jev-decision-index/raw/main/data/index-v0.3.2.json>
- The downloaded historical data identifies its generation time as
  `2026-10-16T16:39:08Z`. Its `meta.org` entries confirm the mappings below
  for StartLux, Cloudflare, vLLM Semantic Router, Perplexity, and TypeSafe.
- The current board also offers a newer 0.4 edition. This provenance check
  does not replace the local historical scores with that edition.

## Model-to-publisher mapping

| Local model | Publisher | Verified model or product page | Evidence |
| --- | --- | --- | --- |
| Piccolo | AgentScope | <https://github.com/agentscope-ai/agentscope> | Team identity confirmed by the user. `agentscope.svg` is the unchanged official README logo; Piccolo remains the model display name. Historical `oneshot` result IDs retain their exact publisher mapping. |
| StartLux-Decision v1.1 27B Instant | StartLux Labs / StartLux | <https://huggingface.co/startlux-models/StartLux-Decision-v1.1-27B-Instant> | Historical board `engine=startlux-decision-v1.1-27b-instant`, `meta.org.id=startlux-models`, `meta.org.name=StartLux`; the same model card is linked by the official [StartLux-Decision repository](https://github.com/StartLuxLabs/StartLux-Decision). |
| Strands Decider 26B-A4B (Gemma 4) | Strands Labs / Strands Agents | <https://huggingface.co/StrandsAgents/strands-decider-26B-A4B-gemma4-v1-2610> | The publisher's model card and [official repository](https://github.com/strands-labs/strands-decider) list this exact checkpoint. [Strands Labs](https://github.com/strands-labs) identifies itself as the experimental arm of Strands Agents. Gemma is the base family, not the publisher. |
| Cloudflare Clef (27B) | Cloudflare | <https://huggingface.co/Cloudflare/clef> | Historical board `engine=clef`, `meta.org.id=Cloudflare`; [Cloudflare's announcement](https://blog.cloudflare.com/clef-decision-models/) explicitly describes the Cloudflare-trained Clef models. |
| Microsoft Decision-1 | Microsoft | <https://commandline.microsoft.com/microsoft-decision-1-model-foundry/> | Microsoft's product announcement and [Microsoft Learn documentation](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision) identify Microsoft-Decision-1. |
| Mercury Decide (Inception) | Inception | <https://www.inceptionlabs.ai/blog/introducing-mercury-3> | Inception's official product announcement explicitly includes Mercury Decide in its product portfolio. This is a verified product announcement, not an invented model-card URL. |
| GPT-6 Luna Decisions | OpenAI | <https://developers.openai.com/api/docs/guides/decisions> | OpenAI's official Decisions guide names `gpt-6-luna` as the model for this API. The local label describes the model/API combination. |
| Jev 1.14 | TypeSafe AI | <https://typesafe.ai/blog/jev-1-14> | Historical board reference model `engine=jev`, `version=jev-1.14.0`, `meta.org.id=typesafe-ai`; the TypeSafe release announcement confirms the version. |
| vLLM-SR d3 (27B) | vLLM Semantic Router | <https://huggingface.co/vllm-sr/d3/tree/v3.1.0> | Historical board `engine=vllm-sr-d3-v310`, `meta.org.id=vllm-sr`, `meta.org.name=vLLM Semantic Router`; this exact version URL is the board's `model_url`. The [main model card](https://huggingface.co/vllm-sr/d3) confirms the project. Qwen is the base family, not the publisher. |
| Perplexity Decider v1.2 (27B) | Perplexity | <https://huggingface.co/perplexity-ai/pplx-decider-v1.2> | Historical board `engine=pplx-decider-v1.2`, `meta.org.id=perplexity-ai`, `meta.org.name=Perplexity`; the model card is under the publisher's official organization. |

Strands 26B-A4B, Microsoft Decision-1, Mercury Decide, and GPT-6 Luna
Decisions were verified through their publishers' pages. Their inclusion here
does not assert a matching result in the historical Decision Index snapshot.

## Newly downloaded assets

Each asset comes from the publisher's official website or its official
Hugging Face organization profile. Image bytes are preserved; the OpenAI SVG
is extracted verbatim from its official logo archive. File extensions follow
the actual image format: Hugging Face's
avatar CDN returned WebP from the `.png` URLs below, while Cloudflare's
`favicon.ico` URL returned PNG.

| Local file | Official page identifying the icon | Exact download URL |
| --- | --- | --- |
| `startlux.webp` | <https://huggingface.co/startlux-models> | <https://cdn-avatars.huggingface.co/v1/production/uploads/64d33626465b6039259b9c72/6xsdrTfPBTVyKxaNDVi16.png> |
| `strands.webp` | <https://huggingface.co/StrandsAgents> | <https://cdn-avatars.huggingface.co/v1/production/uploads/6498ef778fadf0ae7639b982/oAm2hXS7rD42MZ7paxeoX.png> |
| `cloudflare.png` | <https://www.cloudflare.com/> | <https://www.cloudflare.com/favicon.ico> |
| `openai.svg` | <https://openai.com/brand/> | <https://cdn.openai.com/brand/OpenAI-Logos-2025.zip> |
| `vllm.webp` | <https://huggingface.co/vllm-sr> | <https://cdn-avatars.huggingface.co/v1/production/uploads/66f8caead3186746f4524419/hEhRBJQ2FfsIPGdREBr5u.png> |
| `perplexity.svg` | <https://www.perplexity.ai/> | <https://www.perplexity.ai/favicon.svg> |

The OpenAI asset is the black, transparent Blossom from
`OpenAI-logos(new)/SVGs/OpenAI-black-monoblossom.svg` inside the official
`OpenAI-Logos-2025.zip` archive (76,633 bytes; SHA-256
`b2c4cd1e86bbe76bdc4946a72d014efa455240c177f4878fd68cc9b88c71d2ec`).
It replaces the blue developer-site favicon. The SVG's paths, black fill,
viewBox, and clear space are unchanged; its transparent background lets the
site's warm white surface show through. The Blossom belongs to OpenAI and
is used here solely to identify the OpenAI model publisher.

The Cloudflare and Perplexity assets are their website favicons.
Organization avatars and favicons are used as compact publisher identifiers;
no new brand artwork was drawn or recolored.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `startlux.webp` | 12884 | `804da33c346954d4f00047ec0934d144b1f149f8bee694070c871afff770e72d` |
| `strands.webp` | 8456 | `c6306d616ed2d18e075aeb1ef8016c72d42c9ebc2c33ac53dda95d3f375cd369` |
| `cloudflare.png` | 908 | `5414bc6e4b3f6e10f99b5d37abf4420da4dcaece66f8f2c08e090e87267adbc5` |
| `openai.svg` | 2969 | `7be72f1fea831d3ba81a545cee79b7e0ae69449d5d7837c9571ccbfb4aa1e00b` |
| `vllm.webp` | 4712 | `5bf03abcbfe732e9690017a304f28a85d638e1d8417903b6a274dd6aba8e18fe` |
| `perplexity.svg` | 2438 | `00180a688c194d684a69b247769cdf24a7720712256dbe0f334f97e8a15821e4` |

## Existing assets

`oneshot.svg`, `microsoft.ico`, `inception.png`, and `typesafe.png` were not
modified by this source/asset update. Their previously recorded sources
remain in [README.md](README.md). Qwen and other existing brand assets also
remain unchanged. All icons are served locally by the frontend.
