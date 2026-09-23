import sys
sys.path.insert(0, '/home/thomas/LivingCode/Projects/elemental-life-2')
import elemental_life_2_core as m

e = m.ElementalLife2Engine(config={'max_cycles': 5})
e.evolve(); e.evolve()
raw = e.state_history[0]
print('raw history[0] is live.metrics ->', raw.metrics is e.state.metrics)
print('raw history[0] change_log is live.change_log ->', raw.change_log is e.state.change_log)
print('raw history[0] metrics:', raw.metrics)
print('live state metrics:', e.state.metrics)