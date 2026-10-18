### A silly bot to ping Juni and do silly things

# What is this bot?

Junibot was created with the idea of ​​pinging Juni (a friend), as time went on more new features were implemented for various conveniences.

## Estadísticas de juegos

Usa `/stats juego:Wordle` o `/stats juego:Sudoku` para consultar tus resultados.
Las estadísticas de Sudoku incluyen victorias, victorias por dificultad y mejor tiempo.

Para guardar las victorias de Sudoku, configura `DISCORD_CLIENT_SECRET` como variable
de entorno del proceso que ejecuta `web_app.py`. Se obtiene en el portal de
desarrolladores de Discord y permite validar la identidad del jugador de la Activity;
no debe guardarse en el repositorio ni exponerse al cliente.
