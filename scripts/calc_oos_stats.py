import sqlite3, numpy as np, scipy.stats as st
conn = sqlite3.connect('data/final_oos_validation.sqlite')
pnls = [r[0] for r in conn.execute("SELECT realized_pnl FROM paper_closed_positions WHERE portfolio_id LIKE '%_on'").fetchall()]
n = len(pnls)
wins = sum(1 for p in pnls if p > 0)
wr = wins / n
wr_ci = st.norm.interval(0.95, loc=wr, scale=np.sqrt(wr*(1-wr)/n))
exp = np.mean(pnls)
exp_ci = st.t.interval(0.95, df=n-1, loc=exp, scale=st.sem(pnls))
np.random.seed(42)
boots = [np.sum(np.random.choice(pnls, n, replace=True)) for _ in range(10000)]
pnl_ci = np.percentile(boots, [2.5, 97.5])
long_short = conn.execute("SELECT direction, SUM(realized_pnl) FROM paper_closed_positions WHERE portfolio_id LIKE '%_on' GROUP BY direction").fetchall()
tf_asset = conn.execute("SELECT portfolio_id, SUM(realized_pnl) FROM paper_closed_positions WHERE portfolio_id LIKE '%_on' GROUP BY portfolio_id ORDER BY SUM(realized_pnl) DESC").fetchall()

print(f'N: {n}')
print(f'WR_CI: {wr_ci}')
print(f'EXP_CI: {exp_ci}')
print(f'PNL_CI: {pnl_ci}')
print(f'LONG_SHORT: {long_short}')
print(f'TF_ASSET: {tf_asset[:3]}')
