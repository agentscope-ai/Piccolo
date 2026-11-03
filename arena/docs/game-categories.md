# Playground game categories

The game selector, browser catalog and Arena radar use the same category mapping in `web/playground/game-categories.js` and active scope in `config/game-scope.json`.

| Category | Games | Count |
| --- | --- | ---: |
| Probability | Liar's Dice, Dou Dizhu, UNO, Guess the Number, Minesweeper | 5 |
| Strategy | Othello 6×6, Hex, Chess, Checkers, Xiangqi | 5 |
| Long-horizon | 2048, Sokoban, Property Tycoon, Sudoku | 4 |
| Real-time | Terraria, Tetris, Snake | 3 |

The current playground contains **17 games**. Dots and Boxes, Blackjack, Texas Hold'em, Zha Jin Hua and Mario are excluded from the selectors and new-session APIs. Their historical results, recordings and engine implementations remain available.

Each game appears in one category. Categories describe the main decision pattern: uncertainty, board strategy, multi-step planning or real-time control.

The radar displays the 17 active game dimensions in four category quadrants. Historical Elo snapshots are projected onto the active scope, and the overall rating uses an equal mean of the remaining per-game Elo ratings. This display projection leaves the archived results unchanged.

Game icons use the bundled Noto Emoji subset; see `web/playground/fonts/NotoGameEmoji-LICENSE.txt`.
