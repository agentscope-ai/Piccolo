// Technical release article edited from the team's local source manuscript.
// Public comparison scores and full-suite research results use separate scopes.
export const article = {
  "en": {
    "title": "Piccolo",
    "subtitle": "Recursively self-improving decision models",
    "deck": "27B, 9B and 4B models for intelligent routing in harnesses, data workflows and successive decisions in games.",
    "readTime": "18–22 min · technical report",
    "intro": [
      "Piccolo-27B-VL ranks first on Decision Index Vision Full with 75.59. Piccolo-9B-VL scores 68.35 and Piccolo-4B-VL scores 67.46.",
      "From tool review and context selection in agent harnesses, to decisions in data workflows and successive moves in games, Piccolo interprets the current state, compares candidates and returns results and probabilities that programs can use directly. To develop the Piccolo family, we designed a research framework around recursive self-improvement (RSI): research agents use model errors and training feedback to select data, test changes and choose the next experiment. This report presents Piccolo’s applications, benchmark results and development process."
    ],
    "sections": [
      {
        "id": "decision",
        "nav": "See decisions at work",
        "kicker": "DEMO SHOWCASE",
        "title": "See decisions at work",
        "paragraphs": [
          "Across successive actions in games, execution control inside an agent harness and judgments throughout a data workflow, these three settings show how Piccolo turns the current state into decisions that programs can use."
        ],
        "leadParagraphs": 1,
        "headingLevel": 2,
        "takeaway": ""
      },
      {
        "id": "demogames",
        "nav": "Game · successive decisions",
        "kicker": "2.1 / GAME",
        "title": "Game · successive decisions",
        "paragraphs": [
          "Nine game recordings are grouped into action, puzzle and board games. Mario tests jump timing, 2048 tests merge direction and Sokoban tests box-to-goal assignments. The 95-second Zenless Zone Zero combat recording shows the active controls alongside the character’s movements, attacks and dodges."
        ],
        "leadParagraphs": 1,
        "headingLevel": 3,
        "takeaway": ""
      },
      {
        "id": "demoharness",
        "nav": "Harness · decide what the agent may do next",
        "kicker": "2.2 / HARNESS",
        "title": "Harness · decide what the agent may do next",
        "paragraphs": [
          "Help your agent choose the right tool, stay within its permissions and budget, and verify results before completing a task. Piccolo evaluates the task requirements and execution evidence to choose the next action; the workflow then carries out that decision.",
          "Choose a case below to see the inputs Piccolo receives, the decision it makes and what happens next: execute a tool, request missing evidence, or pause for review."
        ],
        "leadParagraphs": 2,
        "headingLevel": 3,
        "takeaway": ""
      },
      {
        "id": "demodata",
        "nav": "Data · judge the next step in a workflow",
        "kicker": "2.3 / DATA",
        "title": "Data · judge the next step in a workflow",
        "paragraphs": [
          "Decide which records to keep, how to clean them and whether the results are ready to use or share. Piccolo evaluates the source material, quality requirements and validation results to select the next step in your data workflow.",
          "Choose a case below to see the data Piccolo receives, the judgment it makes and the resulting action: accept or reject a record, select a processing plan, request more information, or return an output for correction."
        ],
        "leadParagraphs": 2,
        "headingLevel": 3,
        "takeaway": ""
      },
      {
        "id": "evidence",
        "nav": "Benchmark Evaluation",
        "kicker": "BENCHMARK EVALUATION",
        "title": "Benchmark evaluation",
        "paragraphs": [
          "Piccolo-27B-VL ranked first on Decision Index Vision Full with **75.59**. Its Public and Private scores were **80.22** and **70.97**. Piccolo-9B-VL and Piccolo-4B-VL scored **68.35** and **67.46** on Vision Full.",
          "The foundation models scored **68.40**, **57.34** and **50.00** on Decision Index Text Full for 27B, 9B and 4B. On JevBench-231, their accuracies were 92.21%, 89.61% and 87.01%. HarnessJevBench Hard scores were 84.41%, 70.68% and 63.22%. DataJevBench accuracies were 82.60%, 69.20% and 71.20%."
        ],
        "takeaway": ""
      },
      {
        "id": "method",
        "nav": "Method",
        "kicker": "04 / METHOD",
        "title": "Method: Agentic Iteration",
        "headingLevel": 2,
        "paragraphTitles": [
          ""
        ],
        "paragraphs": [
          "We develop Piccolo by iterating on model errors and training feedback. In each round, research agents identify judgments the model needs to improve, select or construct training examples, and run training and evaluation to test the proposed changes. The results guide the data recipe and training choices for the next round. We connect data provenance, semantic tags, per-example learning records and model performance so that agents can trace each change to the data it used and the results it produced. The best 27B model was trained on a cumulative **350,000 examples**."
        ],
        "takeaway": "",
        "media": [
          {
            "id": "method-video",
            "after": 0,
            "kind": "video",
            "label": "VIDEO 1",
            "title": "Piccolo evolution",
            "caption": "Across 10+ rounds and 150+ exploratory experiments, Piccolo evolves through an agent-driven feedback loop. All exploratory experiments together used 6,300 GPU hours on PPU-Zhenwu 810E hardware, covering the full exploration rather than only the best model’s training.",
            "src": "./blog/assets/method-piccolo-evolution.webm",
            "poster": ""
          }
        ]
      },
      {
        "id": "preparation",
        "nav": "Data curation and supervision",
        "kicker": "METHOD / DATA CURATION",
        "title": "4.1 Data curation and supervision",
        "paragraphTitles": [
          "",
          "Using semantic tags to connect data and capabilities",
          "",
          "",
          "Supervising candidate distributions"
        ],
        "paragraphs": [
          "We downloaded and collected **6.65 million records from the open-source community**, covering classification, retrieval, mathematical reasoning, preference judgments and tool use, and curated training material from this collection. We also synthesize targeted environments and construct decision tasks from state transitions, action choices and constraints. Each source is converted into the same structure: state, questions, candidates and target distributions. Hard labels specify a definite choice; soft labels retain distributions over ratings, preferences and judgments. Both use the same training interface. **Before entering the training pool, all data is deduplicated and checked for benchmark overlap, with overlapping material excluded to keep training and evaluation data separate.**",
          "To select data, we first need to know what judgment each example teaches. We build on the [Data-Juicer](https://github.com/datajuicer/data-juicer) framework to annotate examples and group them into slices with shared characteristics. The taxonomy has **13 annotation dimensions and 551 predefined values**, including 334 domain categories and 144 capability tags. It also records task type, decision relationships, difficulty, learning value and quality.",
          "For example, computing and technology identifies a content domain, while constraint reasoning and tool applicability identify the judgments a task requires. Intersecting these tags selects focused groups of examples from broad data sources. Linking them to per-example loss, answer accuracy and experiment results lets us track how the same slice is learned by different models and at different training stages.",
          "Figure 1 shows our data-processing workflow. Domain tags cover everyday life, computing and technology, mathematics and science, arts and humanities, and professional domains. Task formats include candidate selection, binary judgments and numerical scoring. Information processing and reasoning make up most of the capability coverage; tool and environment interaction, safety and compliance, and instruction following add other decision settings. The agent uses the distributions of domain, capability, difficulty and task format to adjust the mix, add underrepresented decision types, adjust question difficulty and retain background data that preserves existing capabilities.",
          "The main supervised training stage uses **cross-entropy over candidate distributions**. For a question with \\(K\\) options, candidate scores \\(z_i\\) are read at the answer position and normalized into probabilities \\(p_i\\), which are aligned with the target distribution \\(y_i\\): \\(p_i=\\frac{\\exp(z_i)}{\\sum_{j=1}^{K}\\exp(z_j)}\\), \\(\\mathcal L_{\\mathrm{CE}}=-\\sum_{i=1}^{K}y_i\\log p_i\\)."
        ],
        "takeaway": "",
        "media": [
          {
            "id": "method-figure-1",
            "after": 3,
            "kind": "image",
            "label": "FIGURE 1",
            "title": "Source governance, semantic annotation and the training-data profile",
            "caption": "Data slices provide a shared reference for recipe construction and model-feedback analysis.",
            "src": "./blog/assets/method-data-curation.png",
            "poster": ""
          }
        ],
        "headingLevel": 3
      },
      {
        "id": "rsi",
        "nav": "Choosing the next experiment from feedback",
        "kicker": "METHOD / AGENTIC DATA ENGINEERING",
        "title": "4.2 Choosing the next experiment from feedback",
        "paragraphTitles": [
          "",
          "Using training dynamics to select data for further learning",
          "",
          "Turning feedback into experiments",
          "",
          "",
          ""
        ],
        "paragraphs": [
          "Once the data is organized, research agents decide **what the model should train on next and how that data should be used**. Our [Agentic Data Engineering](https://github.com/datajuicer/agentic-data-engineering) system organizes this research loop: multiple agents propose plans, run experiments, analyze training and evaluation results, and revise the next recipe. Humans set the objectives, resource budgets and permitted scope of data use. Within that scope, agents diagnose problems, construct data and run experiments, while auditing checks data quality, procedures and results.",
          "The cross-entropy objective decomposes into target entropy and KL loss: \\(\\mathrm{CE}(y,p)=H(y)+\\mathrm{KL}(y\\Vert p)\\). For a given target, \\(H(y)\\) is fixed, while \\(\\mathrm{KL}(y\\Vert p)\\) measures the difference between model predictions and the target distribution. We track per-example KL loss and aggregate it by semantic tags across domains, capabilities and task types to guide data selection and recipe optimization, while distinguishing supervision types, candidate counts and data sources.",
          "When choosing the next experiment from a data slice, we examine the level of KL divergence, how it changes during training, and which task types account for high divergence. In Figure 2, divergence declines steadily for mathematics and science, remains relatively low for computing, and fluctuates for arts and media. Differences averaged away in the overall loss suggest different experiments:\n\n**Steady decline: test how much more the model can learn.** Broaden coverage around the same decision relationship, try continued training or more data, and measure whether the gains persist.\n\n**Low and stable: reduce repeated exposure.** Sample fewer homogeneous templates, retain representative replay examples, and direct more training budget toward slices with further learning potential.\n\n**Persistently high divergence: check supervision before adding data.** Review question conditions and answers, then use semantic retrieval, mixture adjustments or targeted synthesis to add combinations of conditions the model has yet to master.\n\n**Fluctuation or rebound: examine interactions between recipes.** Compare data composition, training settings and capability changes at the corresponding stages, then vary the balance between targeted data and background replay in the next experiments.\n\nThese curves help formulate experimental hypotheses. Training and evaluation still determine whether the proposed changes work.",
          "Each experiment follows **proposal design → construction and experimentation → results and feedback → diagnosis and revision**. The agent specifies the target slices, data operations, training settings and comparison models, then constructs a recipe and runs training and evaluation. It compares overall and category-level results, selects branches for further exploration, and records useful practices with their conditions of use. Better-performing models become starting points for the next round, while results from other branches also inform subsequent choices.",
          "We manage data versions, experiment configurations, model relationships and evaluation results as a connected experiment lineage. Each training run links its input data, parent model, configuration and results. We can trace a model back to its training material and upstream models, or compare a data slice across experiments. Data-processing procedures, evaluation protocols and useful practices are saved with the experiment records for later comparison and reuse.",
          "[DataJuicer-Sandbox](https://github.com/datajuicer/data-juicer-sandbox) executes the experiments by organizing data processing, training and evaluation into workflows that agents can run. Each step specifies its inputs, operation and outputs, and the steps are connected according to the experiment plan. Within the agreed data scope and evaluation definitions, agents can revise recipes, combine or modify processing operators, and adjust training strategies and evaluation implementations. On the data side, they use four main operations:",
          "An experiment can combine these operations. For a high-divergence slice, an agent might review answers, retrieve related material from the existing pool and add more combinations of conditions. Training retains background replay, and evaluation checks both the target capability and existing capabilities. These results determine whether the next round continues or revises the proposal."
        ],
        "takeaway": "",
        "media": [
          {
            "id": "method-figure-2",
            "after": 2,
            "kind": "image",
            "label": "FIGURE 2",
            "title": "From feedback signals to data iteration",
            "caption": "Training dynamics illustrate one diagnostic approach; the agent combines data analysis with inference performance to choose subsequent data operations through experiments.",
            "src": "./blog/assets/method-agentic-data-engineering.png",
            "poster": ""
          }
        ],
        "table": {
          "after": 5,
          "caption": "Four data operations and their intended training effects",
          "headers": [
            "Data operation",
            "Processing",
            "Intended training effect"
          ],
          "rows": [
            [
              "Removal and downsampling",
              "Remove erroneous and duplicate material; adjust exposure to homogeneous examples the model has already learned well.",
              "Allocate training budget to material with more learning potential."
            ],
            [
              "Selection and mixing",
              "Select examples by tags, semantic similarity and learning state; combine background, targeted and replay data.",
              "Strengthen target capabilities while preserving existing ones."
            ],
            [
              "Auditing and rewriting",
              "Complete conditions, correct answers, reconstruct distractors and adjust candidate positions.",
              "Improve supervision quality and reinforce the intended decision relationships."
            ],
            [
              "Targeted synthesis",
              "Construct new examples around target capabilities, task mechanisms and difficulty.",
              "Expand task coverage and create new learning opportunities."
            ]
          ]
        },
        "headingLevel": 3
      },
      {
        "id": "learning",
        "nav": "Model evolution",
        "kicker": "METHOD / MODEL EVOLUTION",
        "title": "4.3 Model evolution",
        "paragraphTitles": [
          "",
          "From data curation to targeted mixtures",
          "Adapting training to the data",
          "Merging complementary branches",
          "Changing how the model reads the input",
          "Reusing the process for 4B and 9B",
          "Extending to image-text inputs",
          "Three lessons from the exploration"
        ],
        "paragraphs": [
          "We begin Piccolo’s development with data and supervision, strengthen specific capabilities, then use the experimental results to adjust training and inference. Figure 3 groups representative results by these stages of exploration. Branches share data recipes, training insights and merged models. As we learn more about the model, data selection moves from source-level mixtures toward specific decision relationships, and training feedback informs the next experiment. The text trajectory uses full-suite text Decision Index (DI); the multimodal branch uses its corresponding image-text evaluation.",
          "The 27B base model starts at **48.91** full-suite DI and reaches **56.68** after initial data curation and training. The agent then adjusts the ratio of background and targeted material using semantic tags, continuing training from better-performing models to reach **59.09**. Data recipes move from source-level mixtures toward selection by task coverage and model performance, while useful checkpoints provide starting points for later training.",
          "We also adjust how the model uses the data. Bidirectional attention lets information within the input interact, candidate supervision aligns learning with decision outputs, and staged training separates broad coverage from targeted strengthening. Representative results reach 60.92 and 62.39. Semantic retrieval, additional preference and tool-use tasks, background replay and model merging then bring results to 63.84 and into the 65-point range. Data selection becomes more specific to tool applicability, information sufficiency and candidate preferences.",
          "Separate branches strengthen knowledge, preferences or tool use. We select complementary models by their category-level results and merge them. One five-branch merge reaches **63.11** full-suite DI, compared with **62.78** for the best single branch at that stage. The agent retains each branch's recipe and results, so later experiments can continue training those models or reuse effective data choices.",
          "Input organization is also part of the iteration. The agent searches over the order of questions and context, question-first layouts and repeated reading, alongside data recipes and training settings. We call this exploration **Context evolving**. In a comparison **with model weights held fixed**, changes to input and inference settings raise full-suite DI from **65.05 to 66.19**. Further matching training inputs, attention and targeted data produces representative results of 66.65, 67.44 and 68.33. Subsequent data selection and supplementation using per-example learning feedback reach **68.59** full-suite DI.",
          "We apply the same data-engineering process to 4B and 9B models. Under the same inference settings as the 27B model, 9B improves from its base score of **46.78 to 60.86**. Recipe reconstruction, learning-signal selection and complementary branch merging raise 4B from **39.94 to 58.00**. The agent uses tags and response feedback to adjust difficulty, data mixtures and replay ratios for the new model, drawing on task experience from earlier experiments.",
          "Multimodal experiments first adjust the organization of images, questions and candidates, then train the visual connector and visual capabilities. Multimodal DI improves from **70.45 to 73.41**. A subsequent merge of image-text and text branches achieves **68.19 text DI and 73.03 multimodal DI** in one model, showing that the two branches' capabilities can be combined.",
          "**Recipes are more targeted when they specify the judgment to learn.** Moving beyond broad domain coverage to slices for conditional constraints, tool applicability and candidate preferences makes it clearer which examples to add and what the model should learn.\n\n**Data, training and input organization need to be considered together.** Supervision distributions, attention settings and input structure all affect candidate judgments. Coordinating them around the same decision interface helps the model use the relationships learned in training during inference.\n\n**Retain models and experiment records for the next iteration.** Strong checkpoints can be trained further, complementary branches can be merged, and recipes and per-example learning records can guide new data selections. These results support the next iteration."
        ],
        "takeaway": "",
        "media": [
          {
            "id": "method-figure-3",
            "after": 0,
            "kind": "image",
            "label": "FIGURE 3",
            "title": "Connected explorations across the Piccolo family",
            "caption": "Data curation and mixing, training methods and capability development, reading strategies and model-family expansion. The text trajectory reports full-suite DI; the multimodal branch reports corresponding image–text results.",
            "src": "./blog/assets/method-model-evolution.png",
            "poster": ""
          }
        ],
        "leadParagraphs": 1,
        "headingLevel": 3
      },
      {
        "id": "harness",
        "nav": "HarnessJevBench",
        "kicker": "BUILT-IN BENCHMARKS",
        "title": "Built-in benchmarks",
        "paragraphTitles": [
          "",
          "HarnessJevBench"
        ],
        "paragraphs": [
          "We built benchmarks for Harness, Data and Game settings to evaluate decision models in agent execution, data workflows and sequential gameplay.",
          "Agent harnesses are an important application for decision models. We designed [HarnessJevBench](https://github.com/agentscope-ai/HarnessJevBench) to test the decisions that control an agent’s execution: which tool or resource to use, what context to retain, whether an action is authorized and whether the evidence supports completion. Each case supplies the state, evidence and rules, allowing these judgments to be examined individually. The benchmark covers six scenario categories and 29 task types, with 325 evaluation cases in total.",
          "Piccolo-27B achieves **84.41% Hard accuracy**, a macro average over 295 determinate-answer evaluation cases, and **0.2175 total variation distance** from the reference distributions. It scores 96.08% on completion and evidence checks, 93.22% on permissions and trust boundaries, and 70.00% on resource allocation."
        ],
        "takeaway": "",
        "leadParagraphs": 2
      },
      {
        "id": "data",
        "nav": "DataJevBench",
        "kicker": "BUILT-IN BENCHMARKS / DATAJEVBENCH",
        "title": "DataJevBench",
        "paragraphs": [
          "We designed [DataJevBench](https://github.com/datajuicer/DataJevBench) to test decisions inside data workflows: admit a record, select a processing plan, assess an artifact, check whether evidence is sufficient, verify a claim or choose the next action. A plausible summary may contain an unsupported conclusion; a complete-looking table may lack the detail needed for an analysis. The 500 tasks make these judgments explicit, with 480 choice and 20 ordered-scoring questions across six subsets.",
          "Piccolo-27B reaches **82.60% accuracy (413/500)**, exceeding 80% in five subsets. Artifact quality reaches **92.50% (74/80)** and information sufficiency **82.00% (82/100)**; workflow control reaches **91.67% (55/60)**. Overall ECE10 is 0.0746 and Brier is 0.2681. The repository provides the task definitions, probability metrics and full results."
        ],
        "takeaway": "",
        "leadParagraphs": 1
      },
      {
        "id": "future",
        "nav": "Future Directions",
        "kicker": "FUTURE DIRECTIONS",
        "title": "Future directions",
        "paragraphs": [
          "We will continue studying how training and evaluation feedback can guide the next experiment, while strengthening Piccolo’s cross-modal capabilities and its performance over longer decision sequences."
        ],
        "takeaway": ""
      }
    ],
    "futureDirections": [
      {
        "title": "Improve RSI exploration efficiency",
        "text": "Compare experiment-selection strategies through training and evaluation cost, candidate adoption and recipe reuse to make better use of a fixed budget."
      },
      {
        "title": "Strengthen cross-modal capabilities",
        "text": "Strengthen decision models’ ability to understand and jointly reason over information from text, images and other modalities."
      },
      {
        "title": "Improve long-horizon and real-time decisions",
        "text": "Improve the coherence of multi-step actions and end-to-end task performance in games, computer use and browser use."
      },
      {
        "title": "Expand System 1 primitives",
        "text": "Extend System 1 fast thinking beyond choice, score and noul. Develop new structured primitives, with corresponding supervision and evaluation, to broaden the model’s decision capabilities."
      }
    ],
    "benchmarkNotes": "Vision and Text scores use the Decision Index scale of 0–100. The charts show Public scores. The performance summary reports Vision Full. JevBench, HarnessJevBench and DataJevBench show the published application results for the foundation models.",
    "sources": [
      {
        "label": "Piccolo",
        "url": "https://github.com/agentscope-ai/Piccolo",
        "description": "Models and project code."
      },
      {
        "label": "Hugging Face",
        "url": "https://huggingface.co/agentscope-ai/Piccolo-27B",
        "description": "Piccolo model weights."
      },
      {
        "label": "ModelScope",
        "url": "https://www.modelscope.cn/models/AgentScope/Piccolo-27B",
        "description": "Piccolo downloads and usage guides."
      },
      {
        "label": "QwenPaw",
        "url": "https://decisionplayground.agentscope.io/piccolo.html#qwenpaw-showcase",
        "description": "Recorded multi-step payout audit and local tool review."
      },
      {
        "label": "JevBench",
        "url": "https://github.com/fstandhartinger/jevbench",
        "description": "Original benchmark and evaluation protocol."
      },
      {
        "label": "Decision Index",
        "url": "https://huggingface.co/spaces/multimodalart/jev-decision-index",
        "description": "The original Decision Index leaderboard."
      },
      {
        "label": "HarnessJevBench",
        "url": "https://github.com/agentscope-ai/HarnessJevBench",
        "description": "Harness tasks, methodology and results."
      },
      {
        "label": "DataJevBench",
        "url": "https://github.com/datajuicer/DataJevBench",
        "description": "Data workflow tasks and evaluation."
      },
      {
        "label": "Agentic Data Engineering",
        "url": "https://github.com/datajuicer/agentic-data-engineering",
        "description": "Organizes research agents that propose, execute and analyze data experiments."
      },
      {
        "label": "Data-Juicer",
        "url": "https://github.com/datajuicer/data-juicer",
        "description": "Processing, annotation and data slices."
      },
      {
        "label": "DataJuicer-Sandbox",
        "url": "https://github.com/datajuicer/data-juicer-sandbox",
        "description": "Organizes data processing, training and evaluation into executable experiments."
      },
      {
        "label": "CuES",
        "url": "https://arxiv.org/abs/2512.01311",
        "description": "A framework for exploring environments and constructing training tasks from interactions."
      }
    ],
    "contents": [
      {
        "id": "articleIntro",
        "label": "Introduction"
      },
      {
        "id": "decision",
        "label": "Demo Showcase",
        "children": [
          {
            "id": "demogames",
            "label": "Game"
          },
          {
            "id": "demoharness",
            "label": "Harness"
          },
          {
            "id": "demodata",
            "label": "Data"
          }
        ]
      },
      {
        "id": "evidence",
        "label": "Benchmark Evaluation"
      },
      {
        "id": "method",
        "label": "Method",
        "children": [
          {
            "id": "preparation",
            "label": "Data curation and supervision"
          },
          {
            "id": "rsi",
            "label": "Choosing the next experiment from feedback"
          },
          {
            "id": "learning",
            "label": "Model evolution"
          }
        ]
      },
      {
        "id": "harness",
        "label": "Built-in Benchmarks",
        "children": [
          {
            "id": "harness",
            "label": "HarnessJevBench"
          },
          {
            "id": "data",
            "label": "DataJevBench"
          }
        ]
      },
      {
        "id": "future",
        "label": "Future Directions"
      }
    ]
  },
  "zh": {
    "title": "Piccolo",
    "subtitle": "递归自我进化的决策模型",
    "deck": "27B、9B、4B 三个尺寸，面向 Harness 中的智能路由、数据工作流，以及游戏中的连续决策。",
    "readTime": "18–22 分钟 · 技术报告",
    "intro": [
      "Piccolo-27B-VL ranks first on Decision Index Vision Full with 75.59. Piccolo-9B-VL scores 68.35 and Piccolo-4B-VL scores 67.46.",
      "从智能体的工具审核与上下文筛选，到数据处理环境中的关键决策，再到游戏场景下的连续判断，Piccolo 理解当前状态、比较候选项，返回程序可以直接使用的结果与概率。为迭代 Piccolo 系列，我们设计了一套基于递归自改进（RSI）的研发框架：研究 Agent 根据模型的错误和训练反馈选择数据、检验改动，并决定下一轮实验。本文介绍 Piccolo 的应用场景、榜单表现与迭代过程。"
    ],
    "sections": [
      {
        "id": "decision",
        "nav": "看见每一次判断如何影响下一步",
        "kicker": "DEMO SHOWCASE",
        "title": "看见每一次判断如何影响下一步",
        "paragraphs": [
          "从游戏中的连续动作，到智能体 Harness 中的执行控制，再到数据工作流中的关键判断，三个场景展示 Piccolo 如何把当前状态转化为程序可以使用的决策。"
        ],
        "leadParagraphs": 1,
        "headingLevel": 2,
        "takeaway": ""
      },
      {
        "id": "demogames",
        "nav": "Game · 连续动作中的判断",
        "kicker": "2.1 / GAME",
        "title": "Game · 连续动作中的判断",
        "paragraphs": [
          "九个游戏回放按动作、益智和棋盘对局排列。Mario 关注跳跃时机，2048 关注合并方向，推箱子关注箱子与目标的分配。《绝区零》的 95 秒战斗实录将按键和游戏画面放在一起，可以对照角色何时移动、攻击和闪避。"
        ],
        "leadParagraphs": 1,
        "headingLevel": 3,
        "takeaway": ""
      },
      {
        "id": "demoharness",
        "nav": "Harness · 决定 Agent 的下一步",
        "kicker": "2.2 / HARNESS",
        "title": "Harness · 决定 Agent 的下一步",
        "paragraphs": [
          "让 Agent 选对工具、遵守权限与预算，并在结束任务前确认结果。Piccolo 结合任务要求与执行证据，判断下一步应该做什么，再由工作流落实这个决定。",
          "选择下方案例，查看 Piccolo 收到了哪些材料、作出了什么判断，以及判断如何改变下一步：调用工具、补充证据，或暂停并请求复核。"
        ],
        "leadParagraphs": 2,
        "headingLevel": 3,
        "takeaway": ""
      },
      {
        "id": "demodata",
        "nav": "Data · 判断数据处理该如何继续",
        "kicker": "2.3 / DATA",
        "title": "Data · 判断数据处理该如何继续",
        "paragraphs": [
          "判断哪些数据该保留、如何清洗，以及处理结果能否使用或对外分享。Piccolo 结合原始材料、质量要求与校验结果，选择数据工作流的下一步动作。",
          "选择下方案例，查看 Piccolo 收到了哪些数据、作出了什么判断，以及判断后的处理动作：收录或剔除记录、选择清洗方案、请求补充信息，或将产物退回更正。"
        ],
        "leadParagraphs": 2,
        "headingLevel": 3,
        "takeaway": ""
      },
      {
        "id": "evidence",
        "nav": "基准评测",
        "kicker": "BENCHMARK EVALUATION",
        "title": "基准评测",
        "paragraphs": [
          "Piccolo-27B-VL ranked first on Decision Index Vision Full with **75.59**. Its Public and Private scores were **80.22** and **70.97**. Piccolo-9B-VL and Piccolo-4B-VL scored **68.35** and **67.46** on Vision Full.",
          "The foundation models scored **68.40**, **57.34** and **50.00** on Decision Index Text Full for 27B, 9B and 4B. On JevBench-231, their accuracies were 92.21%, 89.61% and 87.01%. HarnessJevBench Hard scores were 84.41%, 70.68% and 63.22%. DataJevBench accuracies were 82.60%, 69.20% and 71.20%."
        ],
        "takeaway": ""
      },
      {
        "id": "method",
        "nav": "方法",
        "kicker": "04 / METHOD",
        "title": "方法：智能体驱动的迭代",
        "headingLevel": 2,
        "paragraphTitles": [
          ""
        ],
        "paragraphs": [
          "我们围绕当前模型的错误和训练反馈迭代 Piccolo。每一轮，研究 Agent 先找出需要补足的判断能力，再从数据池中选择或构造训练材料，运行训练与评测，检查改动是否有效。下一轮实验由这些结果出发，继续调整数据配方与训练方式。要支持这一过程，我们把数据来源、语义标签、逐题学习记录和模型表现关联起来，让 Agent 能追踪每次改动用了什么数据、得到了什么结果。最优 27B 模型累计训练了 **35 万条样本**。"
        ],
        "takeaway": "",
        "media": [
          {
            "id": "method-video",
            "after": 0,
            "kind": "video",
            "label": "视频一",
            "title": "Piccolo 演化轨迹",
            "caption": "在 Agent 驱动的迭代闭环中，10+ 轮、150+ 探索实验沿着反馈持续演进。 全部探索实验合计使用了 6,300 GPU hours（PPU-真武810E），该算力总量并非仅用于训练最优模型。",
            "src": "./blog/assets/method-piccolo-evolution.webm",
            "poster": ""
          }
        ]
      },
      {
        "id": "preparation",
        "nav": "数据整理与监督",
        "kicker": "METHOD / 数据整理",
        "title": "4.1 数据整理与监督",
        "paragraphTitles": [
          "",
          "用语义标签定位数据与能力",
          "",
          "",
          "用候选分布表示监督目标"
        ],
        "paragraphs": [
          "我们从开源社区下载和收集了 **665 万条数据**，覆盖分类、检索、数理推理、偏好判断与工具使用等任务，并从中整理训练材料。我们还定向合成环境，从状态变化、行动选择和约束关系中构造决策任务。不同来源的数据统一为“状态、问题、候选项、目标分布”：硬标签给出确定选择，软标签保留评分、偏好与判断的分布，两者使用同一个训练接口。**所有数据在入池前统一去重，并检查和排除与 Benchmark 的重叠，确保训练与评测数据隔离。**",
          "选择数据之前，需要先知道每条样本训练什么判断。我们基于 [Data-Juicer](https://github.com/datajuicer/data-juicer) 框架对样本进行标注和切片，即按标签选出具有共同特征的一组数据。标签体系包含 **13 个标注维度、551 个预定义取值**，其中有 334 个领域细类、144 个能力标签，还记录任务类型、决策关系、难度、学习价值和质量等信息。",
          "例如，“计算与技术”描述内容领域，“约束推理”和“工具适用性”描述任务要求的判断。交叉使用这些标签，就能从宽泛的数据来源中选出目标明确的样本。再关联逐题损失、作答通过率和实验结果，可以追踪同一组数据在不同模型、不同训练阶段的学习情况。",
          "图一展示我们的数据处理过程。领域标签包括日常生活、计算与技术、数理科学、人文艺术及专业行业，任务形式包括候选选择、是非判断和数值评分。信息处理与推理占主要部分，工具与环境、安全与合规、指令遵循等材料补充其他决策场景。Agent 结合领域、能力、难度和任务形式的分布调整配比：补充不足的判断类型、调整题目难度，并保留维持已有能力的背景数据。",
          "主要监督阶段直接学习候选项上的概率分布，训练目标是**候选分布交叉熵**。对包含 \\(K\\) 个选项的问题，在回答位置读取候选分数 \\(z_i\\)，得到概率 \\(p_i\\)，与目标分布 \\(y_i\\) 对齐： \\(p_i=\\frac{\\exp(z_i)}{\\sum_{j=1}^{K}\\exp(z_j)}\\)，\\(\\mathcal L_{\\mathrm{CE}}=-\\sum_{i=1}^{K}y_i\\log p_i\\)。"
        ],
        "takeaway": "",
        "media": [
          {
            "id": "method-figure-1",
            "after": 3,
            "kind": "image",
            "label": "图一",
            "title": "来源治理、语义标注与训练数据画像",
            "caption": "数据切片为配方构建和模型反馈分析提供共同坐标。",
            "src": "./blog/assets/method-data-curation.png",
            "poster": ""
          }
        ],
        "headingLevel": 3
      },
      {
        "id": "rsi",
        "nav": "用反馈选择下一轮实验",
        "kicker": "METHOD / AGENTIC DATA ENGINEERING",
        "title": "4.2 用反馈选择下一轮实验",
        "paragraphTitles": [
          "",
          "用训练动态定位值得继续学习的数据",
          "",
          "把反馈转化为实验",
          "",
          "",
          ""
        ],
        "paragraphs": [
          "数据整理好之后，研究 Agent 需要决定**下一轮训练什么，以及怎样使用这些数据**。我们自研的 [Agentic Data Engineering](https://github.com/datajuicer/agentic-data-engineering) 系统负责组织这一研究循环：多个 Agent 分工提出方案、执行实验、分析训练与评测结果，再调整下一轮配方。人类设定目标、资源预算和数据使用范围；Agent 在这个范围内完成诊断、数据构建与实验，审计环节检查数据质量、流程和结果。",
          "交叉熵优化目标可以拆为目标分布的熵和 KL 损失两项： \\(\\mathrm{CE}(y,p)=H(y)+\\mathrm{KL}(y\\Vert p)\\)。对给定标签，\\(H(y)\\) 是固定的，\\(\\mathrm{KL}(y\\Vert p)\\) 衡量模型预测与目标分布的差异。我们观测逐题 KL 损失，并按语义标签汇总不同领域、能力和任务类型的学习情况，用于指导数据选择与配方寻优；分析时同时区分监督形式、候选数量和数据来源。",
          "从数据切片选择下一轮实验时，我们关注 KL 偏差的水平、随训练的变化，以及高偏差集中在哪些题型。图二中，数理类的偏差持续下降，计算机类整体较低，艺术媒体类仍有明显波动。总损失中被平均掉的差异，可以据此转化为不同的实验方向：\n\n**持续下降：探索还能学到多少。** 围绕相同的判断关系增加数据覆盖，尝试续训或扩大数据量，观察收益能否持续。\n\n**低位稳定：减少重复曝光。** 降低同质模板的采样量，保留有代表性的回放，把更多训练预算用于仍有学习空间的切片。\n\n**偏差持续较高：先检查监督，再补充数据。** 复核题目条件和答案，再通过语义检索、配比调整或定向合成，补充模型尚未掌握的条件组合。\n\n**波动或回升：检查配方之间的相互影响。** 对照相应阶段的数据构成、训练设置和能力变化，在下一轮实验中调整目标数据与背景回放的比例。\n\n这些曲线帮助提出实验假设，具体改动是否有效，仍需通过训练与评测检验。",
          "一轮实验按**方案设计 → 构建与实验 → 结果反馈 → 诊断与更新**推进。Agent 先明确目标切片、数据操作、训练设置和比较对象，再构建配方，完成训练与评测。随后比较总分和分项变化，决定哪些分支继续探索，并记录有效做法及其适用条件。表现较好的模型成为下一轮起点，其他分支的结果也用于分析后续应该尝试什么。",
          "我们统一管理数据版本、实验配置、模型之间的关系和评测结果，建立完整的实验血缘（lineage）。每次训练都关联输入数据、父模型、配置和所得结果，既能从模型追溯训练材料和上游模型，也能沿数据切片比较不同实验中的表现。数据处理流程、评测协议和有效做法也随实验记录保存，供后续比较和复用。",
          "实验由 [DataJuicer-Sandbox](https://github.com/datajuicer/data-juicer-sandbox) 执行，它把数据处理、训练和评测组织成 Agent 可以运行的工作流。每一步明确输入、处理方式和产出，再按实验方案连接起来。在约定的数据范围与评测口径下，Agent 除了调整数据配方，也可以组合或修改处理算子、调整训练策略和评测实现。数据侧主要有以下四类操作：",
          "四类操作可以组合使用。例如，对一个高偏差切片，Agent 可以先复核答案，从已有数据池检索相近材料，再补充更多条件组合。训练时保留背景数据回放，评测时同时检查目标能力和已有能力的变化。这些结果决定下一轮是否继续使用或调整该方案。"
        ],
        "takeaway": "",
        "media": [
          {
            "id": "method-figure-2",
            "after": 2,
            "kind": "image",
            "label": "图二",
            "title": "从反馈信号到数据迭代",
            "caption": "训练动态展示一种诊断方式；Agent 结合数据分析与推理表现，在实验中选择后续的数据操作。",
            "src": "./blog/assets/method-agentic-data-engineering.png",
            "poster": ""
          }
        ],
        "table": {
          "after": 5,
          "caption": "四类数据动作及其关注的训练效果",
          "headers": [
            "数据动作",
            "具体处理",
            "关注的训练效果"
          ],
          "rows": [
            [
              "删除与降采样",
              "清理错误与重复材料，调整已充分学习的同质样本曝光",
              "将训练预算分配给更有学习空间的内容"
            ],
            [
              "筛选与配比",
              "按标签、语义相似度和学习状态选题，组合背景、定向与回放数据",
              "加强目标能力，同时保持已有能力"
            ],
            [
              "审计与改写",
              "补齐条件、校正答案、重构干扰项，调整候选位置",
              "提高监督质量，强化预期的判断关系"
            ],
            [
              "定向合成",
              "围绕目标能力、任务机制和难度构造新题",
              "扩展任务覆盖，提供新的学习机会"
            ]
          ]
        },
        "headingLevel": 3
      },
      {
        "id": "learning",
        "nav": "模型演进",
        "kicker": "METHOD / 模型演进",
        "title": "4.3 模型演进",
        "paragraphTitles": [
          "",
          "从数据整理到定向配比",
          "配合数据调整训练方式",
          "合并互补的模型分支",
          "调整读题方式",
          "复用到 4B 与 9B",
          "扩展到图文输入",
          "三点关键经验"
        ],
        "paragraphs": [
          "Piccolo 的迭代从数据与监督入手，逐步补齐具体能力，再结合实验结果调整训练和推理方式。图三按这些探索阶段组织代表性结果，各条分支通过数据配方、训练经验和模型合并相互连接。随着对模型的了解加深，数据选择也从来源配比细化到具体的判断关系，训练反馈逐步用于下一轮设计。文本主线使用全集文本 Decision Index（DI），多模态分支使用相应的图文评测。",
          "27B 基座的全集 DI 为 **48.91**，初步整理数据并训练后达到 **56.68**。随后，Agent 根据标签调整背景与定向材料的比例，从表现较好的模型继续训练，代表性结果达到 **59.09**。这一阶段，数据配方从按来源混合，逐步转向按任务覆盖和模型表现选取；已有的优质模型检查点（checkpoint）则供后续实验继续训练。",
          "我们同时调整模型使用这些数据的方式：双向注意力允许题面信息相互参考，候选监督对齐决策输出，分阶段训练分别安排广泛覆盖和定向加强。代表性结果达到 60.92、62.39。随后加入语义检索、偏好与工具任务、背景回放及模型合并，结果推进到 63.84 和 65 分区间。选题也逐渐细化到工具适用性、信息充分性和候选偏好等具体判断。",
          "不同分支分别加强知识、偏好或工具使用，我们依据分项表现选择互补模型进行合并。一次五分支合并的全集 DI 达到 **63.11**，同阶段最好的单分支为 **62.78**。Agent 同时保留各分支的配方和结果，供后续实验继续训练这些模型，或复用其中有效的数据选择。",
          "输入的组织方式也参与迭代。Agent 将问题与上下文的排列顺序、问题前置和重复阅读等策略纳入搜索，与数据配方和训练设置一起调整，我们将这类探索称为 **Context evolving**。在一组**同权重复测**中，只调整输入与推理设置，全集 DI 从 **65.05 提升到 66.19**。进一步匹配训练输入、注意力与目标数据后，代表性结果经过 66.65、67.44，达到 68.33。随后结合逐题学习反馈筛选和补充数据，取得 **68.59** 的全集 DI。",
          "我们将同一套数据工程方法用于 4B 和 9B。在采用与 27B 相同的推理设置下，9B 从基座的 **46.78 提升到 60.86**；4B 从 **39.94** 经配方重构、学习信号筛选和互补分支合并达到 **58.00**。Agent 根据数据标签和新模型的作答反馈，重新调整题目难度、数据配比与回放比例，复用此前实验中的任务经验。",
          "多模态实验先调整图片、问题和候选的组织方式，再训练视觉连接层与视觉能力，多模态 DI 从 **70.45 提升到 73.41**。随后合并图文与文本分支，在同一模型上取得**文本 DI 68.19、多模态 DI 73.03**，验证了组合两类分支能力的可行性。",
          "**把配方细化到具体判断，数据调整更有针对性。** 从补充某个领域的数据，进一步细分到条件约束、工具适用性和候选偏好，便于明确要补哪些样本、希望模型学会什么。\n\n**数据、训练和读题方式需要一起考虑。** 监督分布、注意力设置和输入组织都影响候选判断。围绕同一决策接口调整这些设置，有助于模型将训练中学到的判断用于实际推理。\n\n**保留模型与实验记录，供下一轮复用。** 好的检查点可以继续训练，互补分支可以合并，配方和逐题学习记录可以帮助重新选题。这些结果共同支持下一轮迭代。"
        ],
        "takeaway": "",
        "media": [
          {
            "id": "method-figure-3",
            "after": 0,
            "kind": "image",
            "label": "图三",
            "title": "Piccolo 系列的相互关联探索",
            "caption": "数据整理与配比、训练方法与能力补齐、读题方式与系列扩展。文本主线展示全集 DI，多模态分支展示相应的图文评测结果。",
            "src": "./blog/assets/method-model-evolution.png",
            "poster": ""
          }
        ],
        "leadParagraphs": 1,
        "headingLevel": 3
      },
      {
        "id": "harness",
        "nav": "HarnessJevBench",
        "kicker": "BUILT-IN BENCHMARKS",
        "title": "内置基准",
        "paragraphTitles": [
          "",
          "HarnessJevBench"
        ],
        "paragraphs": [
          "我们针对 Harness、Data 和 Game 场景自建 Benchmark，评估决策模型在智能体运行控制、数据工作流和游戏连续决策中的表现。",
          "Harness 是决策模型的重要应用场景。我们设计 [HarnessJevBench](https://github.com/agentscope-ai/HarnessJevBench)，单独检验控制智能体运行的判断：选择哪个工具或执行资源、保留什么上下文、操作是否获得授权、证据是否足以支持完成。每个样本给出运行状态、证据与规则，让这些判断可以被逐项检查。基准覆盖 6 类场景、29 个细分任务，共包含 325 个评测样本。",
          "Piccolo-27B 的 **Hard 准确率为 84.41%**，按 295 个确定答案评测样本做宏平均；与参考分布的**总变差距离为 0.2175**。进度验收与证据核验达到 96.08%，权限与信任边界为 93.22%，资源分配为 70.00%。"
        ],
        "takeaway": "",
        "leadParagraphs": 2
      },
      {
        "id": "data",
        "nav": "DataJevBench",
        "kicker": "BUILT-IN BENCHMARKS / DATAJEVBENCH",
        "title": "DataJevBench",
        "paragraphs": [
          "我们设计 [DataJevBench](https://github.com/datajuicer/DataJevBench)，用于检验数据工作流中的决策：记录是否应被收录、采用什么处理方案、产物质量如何、证据是否充分、结论是否成立，以及下一步做什么。摘要可能写得流畅却缺乏来源支持，表格看似完整却缺少分析需要的粒度。基准把这些判断写成明确任务，包含六个子集、500 道题，其中 480 道选择题、20 道有序评分题。",
          "Piccolo-27B 的准确率为 **82.60%（413/500）**，六个子集中五个超过 80%。产物质量达到 **92.50%（74/80）**，信息充分性为 **82.00%（82/100）**，工作流控制为 **91.67%（55/60）**。整体 ECE10 为 0.0746，Brier 为 0.2681。任务定义、概率指标和完整结果见仓库。"
        ],
        "takeaway": "",
        "leadParagraphs": 1
      },
      {
        "id": "future",
        "nav": "未来方向",
        "kicker": "FUTURE DIRECTIONS",
        "title": "未来方向",
        "paragraphs": [
          "接下来，我们会继续研究如何依据训练与评测反馈选择下一轮实验，并强化 Piccolo 的跨模态判断与长程决策能力。"
        ],
        "takeaway": ""
      }
    ],
    "futureDirections": [
      {
        "title": "提高 RSI 探索效率",
        "text": "结合训练与评测开销、候选采用率和配方复用情况，比较实验选择策略，提高有限预算下的有效探索效率。"
      },
      {
        "title": "强化跨模态能力",
        "text": "强化决策模型对文本、图像等不同模态信息的理解与联合判断能力。"
      },
      {
        "title": "提升长程与实时决策能力",
        "text": "面向游戏、computer use 和 browser use 等连续决策场景，提升多步行动的连贯性和最终任务完成效果。"
      },
      {
        "title": "扩充 System 1 原语",
        "text": "System 1 快思考不局限于 choice、score 和 noul。我们将探索更多结构化原语，并建立对应的监督与评测，丰富模型的决策能力。"
      }
    ],
    "benchmarkNotes": "Vision and Text scores use the Decision Index scale of 0–100. The charts show Public scores. The performance summary reports Vision Full. JevBench, HarnessJevBench and DataJevBench show the published application results for the foundation models.",
    "sources": [
      {
        "label": "Piccolo",
        "url": "https://github.com/agentscope-ai/Piccolo",
        "description": "模型与项目代码。"
      },
      {
        "label": "Hugging Face",
        "url": "https://huggingface.co/agentscope-ai/Piccolo-27B",
        "description": "Piccolo 模型权重。"
      },
      {
        "label": "ModelScope",
        "url": "https://www.modelscope.cn/models/AgentScope/Piccolo-27B",
        "description": "Piccolo 模型权重与使用说明。"
      },
      {
        "label": "QwenPaw",
        "url": "https://decisionplayground.agentscope.io/piccolo.html#qwenpaw-showcase",
        "description": "多步结算审计与本地工具审核实录。"
      },
      {
        "label": "JevBench",
        "url": "https://github.com/fstandhartinger/jevbench",
        "description": "原始基准与评测协议。"
      },
      {
        "label": "Decision Index",
        "url": "https://huggingface.co/spaces/multimodalart/jev-decision-index",
        "description": "Decision Index 原始榜单。"
      },
      {
        "label": "HarnessJevBench",
        "url": "https://github.com/agentscope-ai/HarnessJevBench",
        "description": "Harness 任务、方法与结果。"
      },
      {
        "label": "DataJevBench",
        "url": "https://github.com/datajuicer/DataJevBench",
        "description": "数据工作流任务与评测。"
      },
      {
        "label": "Agentic Data Engineering",
        "url": "https://github.com/datajuicer/agentic-data-engineering",
        "description": "组织研究 Agent 提出方案、执行数据实验并分析反馈。"
      },
      {
        "label": "Data-Juicer",
        "url": "https://github.com/datajuicer/data-juicer",
        "description": "数据处理、标注与切片。"
      },
      {
        "label": "DataJuicer-Sandbox",
        "url": "https://github.com/datajuicer/data-juicer-sandbox",
        "description": "将数据处理、训练与评测组织为可执行的实验流程。"
      },
      {
        "label": "CuES",
        "url": "https://arxiv.org/abs/2512.01311",
        "description": "从环境交互中探索并构造训练任务的合成框架。"
      }
    ],
    "contents": [
      {
        "id": "articleIntro",
        "label": "引言"
      },
      {
        "id": "decision",
        "label": "示例展示",
        "children": [
          {
            "id": "demogames",
            "label": "Game"
          },
          {
            "id": "demoharness",
            "label": "Harness"
          },
          {
            "id": "demodata",
            "label": "Data"
          }
        ]
      },
      {
        "id": "evidence",
        "label": "基准评测"
      },
      {
        "id": "method",
        "label": "方法",
        "children": [
          {
            "id": "preparation",
            "label": "数据整理与监督"
          },
          {
            "id": "rsi",
            "label": "用反馈选择下一轮实验"
          },
          {
            "id": "learning",
            "label": "模型演进"
          }
        ]
      },
      {
        "id": "harness",
        "label": "内置基准",
        "children": [
          {
            "id": "harness",
            "label": "HarnessJevBench"
          },
          {
            "id": "data",
            "label": "DataJevBench"
          }
        ]
      },
      {
        "id": "future",
        "label": "未来方向"
      }
    ]
  }
};

// Restricted inline links and structured media keep both language editions and
// the pre-rendered HTML in sync. Pending assets have no URL and make no requests.
export const escapeArticleHTML = value => String(value).replace(/[&<>"']/g,
  character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[character]);

export function renderInline(text, renderText = escapeArticleHTML) {
  // Only explicit emphasis is interpreted; ordinary prose and math still pass
  // through the caller's escaping / KaTeX renderer.
  const emphasize = value => {
    let result = '', offset = 0;
    for (const match of String(value).matchAll(/\*\*([^*\n]+)\*\*|\*([^*\n]+)\*/g)) {
      result += renderText(value.slice(offset, match.index));
      const tag = match[1] !== undefined ? 'strong' : 'em';
      result += '<' + tag + '>' + renderText(match[1] ?? match[2]) + '</' + tag + '>';
      offset = match.index + match[0].length;
    }
    return result + renderText(value.slice(offset));
  };
  let result = '', offset = 0;
  for (const match of String(text).matchAll(/\[([^\]]+)\]\(([^)\s]+)\)/g)) {
    result += emphasize(text.slice(offset, match.index));
    if (/^https:\/\/[^<>"'\s]+$/.test(match[2])) {
      result += '<a href="' + escapeArticleHTML(match[2]) + '" target="_blank" rel="noopener noreferrer">'
        + escapeArticleHTML(match[1]) + '</a>';
    } else result += emphasize(match[0]);
    offset = match.index + match[0].length;
  }
  return result + emphasize(text.slice(offset));
}

export function renderSectionParagraphs(section, start = 0, end = section.paragraphs.length, renderText = escapeArticleHTML) {
  const esc = escapeArticleHTML;
  const body = section.paragraphs.slice(start, end).map((text, offset) => {
    const index = start + offset, title = section.paragraphTitles?.[index];
    const subheading = section.headingLevel === 3 ? 'h4' : 'h3';
    let html = (title ? '<' + subheading + '>' + esc(title) + '</' + subheading + '>\n' : '') + text.split(/\n\n+/).map(paragraph => '<p>' + renderInline(paragraph, renderText) + '</p>').join('\n');
    for (const media of section.media?.filter(item => item.after === index) ?? []) {
      let content;
      if (media.src) {
        for (const src of [media.src, media.mobileSrc].filter(Boolean)) {
          if (!/^\.\/blog\/assets\/[a-zA-Z0-9_./-]+$/.test(src) || src.includes('..')) throw Error('Invalid article media path');
        }
        const img = '<img src="' + esc(media.src) + '" alt="' + esc(media.title) + '" loading="lazy">';
        content = media.kind === 'video'
          ? '<video controls playsinline preload="metadata" aria-label="' + esc(media.title) + '"'
            + (media.poster ? ' poster="' + esc(media.poster) + '"' : '') + ' src="' + esc(media.src) + '"></video>'
          : '<a href="' + esc(media.src) + '" target="_blank" rel="noopener">'
            + (media.mobileSrc ? '<picture><source media="(max-width:800px)" srcset="' + esc(media.mobileSrc) + '">' + img + '</picture>' : img) + '</a>';
      } else {
        content = '<div class="method-media-placeholder"><span>' + esc(media.label) + '</span><strong>'
          + esc(media.title) + '</strong><small>' + esc(section.pendingMedia) + '</small></div>';
      }
      html += '\n<figure class="method-media" id="' + esc(media.id) + '" data-media-kind="' + esc(media.kind)
        + '">' + content + '<figcaption><strong>' + esc(media.label) + ' · ' + esc(media.title)
        + '.</strong> ' + esc(media.caption) + '</figcaption></figure>';
    }
    if (section.example?.after === index) {
      html += '\n<div id="trainingSchema" class="decision-record"><h4>' + esc(section.example.title)
        + '</h4><p>' + esc(section.example.description) + '</p></div>';
    }
    if (section.table?.after === index) {
      const table = section.table;
      html += '\n<div class="method-table-scroll" role="region" aria-label="' + esc(table.caption)
        + '" tabindex="0"><table class="method-operations"><caption>' + esc(table.caption)
        + '</caption><thead><tr>' + table.headers.map(header => '<th scope="col">' + esc(header) + '</th>').join('')
        + '</tr></thead><tbody>' + table.rows.map(row => '<tr>' + row.map((cell, column) => column === 0
          ? '<th scope="row">' + esc(cell) + '</th>' : '<td>' + esc(cell) + '</td>').join('') + '</tr>').join('')
        + '</tbody></table></div>';
    }
    return html;
  }).join('\n');
  const details = section.details && end === section.paragraphs.length && start < end
    ? '\n<details class="research-details"><summary>' + esc(section.details.title) + '</summary><div>'
      + section.details.paragraphs.map(text => '<p>' + renderInline(text, renderText) + '</p>').join('\n')
      + '</div></details>' : '';
  return body + details;
}
