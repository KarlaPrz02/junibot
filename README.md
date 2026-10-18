### A silly bot to ping Juni and do silly things

# What is this bot?

Junibot was created with the idea of ​​pinging Juni (a friend), as time went on more new features were implemented for various conveniences.

## Game statistics

Use `/stats game:Wordle` or `/stats game:Sudoku` to view your results.
Sudoku statistics include wins, wins by difficulty, and your best time.

To save Sudoku wins, set `DISCORD_CLIENT_SECRET` as an environment variable for the
process running `web_app.py`. You can obtain it from the Discord Developer Portal.
It is used to verify the Activity player's identity; **do not** store it in the repository
or expose it to the client.
