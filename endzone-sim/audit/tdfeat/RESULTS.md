# nflfastR stats and TD-location data — tested 2026-09-27, none adopted

Each stat computed from games before kickoff (season to date + last season at weight .3), added to the model's
backtest TD probability (2023–24 actual actives, 2025 pregame, weeks 3+, 13,000 player-games), held out by season.
Log loss change x1000, + = better, 90% bootstrap over games.

| stat | added to model | added to model + DK kickoff price (8,370 quotes) |
|---|---|---|
| end-zone target share vs target share | -0.03 (-0.11 to +0.06) | +0.14 (-0.18 to +0.45) |
| inside-5 carry share vs carry share | -0.04 (-0.32 to +0.23) | -0.50 (-0.84 to -0.16) |
| end-zone + inside-5 raw shares | +0.22 (-0.20 to +0.66) | -0.40 (-0.71 to -0.09) |
| YAC over expected (nflfastR xYAC) | -0.04 (-0.10 to +0.03) | -0.06 (-0.18 to +0.07) |
| team pass rate over expected (nflfastR xpass) | -0.02 (-0.06 to +0.01) | -0.06 (-0.14 to +0.01) |
| red-zone snap share vs snap share (participation) | -0.11 (-0.45 to +0.26) | -0.78 (-1.18 to -0.39) |
| red-zone + inside-5 snap shares (participation) | **+0.74 (+0.16 to +1.33)** | +0.14 (-0.17 to +0.43) |

Receiving yards: prior YAC over expected does not predict the model's yardage miss (RMSE 32.56→32.57, 31.58→31.58, 31.67→31.67).
Team dropback rate: neutral pass rate and pass-over-expected predict a game equally (RMSE .0986 both; both together .0987).

Only red-zone snap share helps the model, and DraftKings already prices it; it is also not published in-season
(participation data for 2026 comes after the season), so paying for it (PFF/FTN routes) is not worth it for this model.
