# Premium dashboard redesign notes

1. **Visual hierarchy first:** the largest element on each screen is the money metric, then status, then supporting KPI rows.
2. **Canvas and grid:** fixed `1600x900`, outer margin `48 px`, internal gap `24 px`, card radii `24–28 px`; this keeps Telegram mobile previews clean and uncluttered.
3. **Dark premium surfaces:** background gradient (`#07111F → #0B1220`) with two card elevations (`#0F1B2D` and `#132238`) for structure without noisy decoration.
4. **Typography scale:** explicit Inter/DejaVu fallback stack with large numeric sizes (`82/56/52/38`) and restrained secondary labels (`20–29`) for readability.
5. **Status color semantics:** success/leader, warning/near goal, danger/gap, info/neutral are mapped consistently to badges, bars and key KPI accents.
6. **Controlled effects:** only local blurred glow behind the main total in the shift summary; no neon borders or decorative line clutter.
7. **Reusable primitives:** all complex blocks are assembled from `draw_rounded_card`, `draw_badge`, `draw_avatar_initials_circle`, `draw_progress_bar`, `draw_main_metric_block`, `draw_small_kpi_card`, `draw_leaderboard_row`, `draw_top_podium_card`.
8. **Dashboard composition:** calm header → dominant "Итоги смены" card → second row with decade + rank context → compact four-card KPI strip.
9. **Leaderboard composition:** calm header → center-focused top-3 podium cards (rank #1 larger) → unified horizontal rows for the rest with special highlight for current user.
10. **Extensibility:** data classes remain the integration boundary; visual components accept typed inputs and can be reused for new report variants.
