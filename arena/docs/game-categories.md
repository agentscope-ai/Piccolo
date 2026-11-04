# Playground game categories

The game selector and browser catalog use the same category mapping in `web/playground/game-categories.js` and active scope in `config/game-scope.json`.

| Category | Games | Count |
| --- | --- | ---: |
| Probability | Liar's Dice, Dou Dizhu, UNO, Guess the Number, Minesweeper | 5 |
| Strategy | Othello 6×6, Hex, Chess, Checkers, Xiangqi | 5 |
| Long-horizon | 2048, Sokoban, Property Tycoon, Sudoku | 4 |
| Real-time | Terraria, Tetris, Snake | 3 |

The current playground contains **17 games**. Dots and Boxes, Blackjack, Texas Hold'em, Zha Jin Hua and Mario are excluded from the selectors and new-session APIs. Their selected showcase recordings and engine implementations remain available.

Each game appears in one category. Categories describe the main decision pattern: uncertainty, board strategy, multi-step planning or real-time control.


Game icons use the bundled Noto Emoji subset; see `web/playground/fonts/NotoGameEmoji-LICENSE.txt`.
