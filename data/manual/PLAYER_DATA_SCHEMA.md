# Field IQ player-game data

Field IQ keeps player performance at game granularity so player features can be joined to a matchup without using future information.

## Canonical record

Each player-game row should include:

- game_id, season, week, game_date, team, opponent, home_away
- player_id when available, player_name, position
- passing: attempts, completions, yards, touchdowns, interceptions, sacks, sack_yards, passer_rating
- rushing: attempts, yards, touchdowns, long
- receiving: targets when available, receptions, yards, touchdowns, long
- defense: total_tackles, solo_tackles, assists, sacks, interceptions, forced_fumbles, safeties
- kicking: field_goals_made, field_goals_attempted and distance buckets when available
- punting/returns: punts, punt_yards, punt_long, punt_average, punt_return_yards, kick_return_yards
- source and source_scope

Missing values remain null. A zero is stored only when the source explicitly reports zero.

## ML rule

For a game at time T, player-derived features may only use games strictly before T. Recommended aggregates are last-3, last-5, and season-to-date values for expected active players. Never train a pregame model with a player's statistics from the game being predicted.

Manual records are reviewed and approved before training. Provider data wins on duplicates.
