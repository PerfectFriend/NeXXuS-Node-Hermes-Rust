// Панель Overview: рендер поверх guardian_status_cmd.
import { formatUptime, statusClass } from '../format.js';

export const OVERVIEW_TAB = 'overview';

/// Заполняет плашки overview из state (см. fetchStatus в main.js).
export function render(root, state) {
  const set = (id, text) => {
    const el = root.getElementById(id);
    if (el) el.textContent = text;
  };
  set('guardian-state', state.guardianState);
  set('guardian-node-id', state.nodeId);
  set('guardian-uptime', formatUptime(state.uptimeMs));
  set('guardian-peers', state.peers);
  set('guardian-chunks', state.chunks);
  set('guardian-epoch', state.epoch);
  set('guardian-tor', state.tor);
  set('guardian-tg', state.monitorEnabled ? 'Активно' : 'Не настроено');

  const stateEl = root.getElementById('guardian-state');
  if (stateEl) {
    stateEl.className = `guardian-stat-value ${statusClass(state.guardianState)}`;
  }

  const btnToggle = root.getElementById('btn-toggle-monitor');
  if (btnToggle) {
    btnToggle.textContent = state.monitorEnabled ? '📊 Мониторинг: ВКЛ' : '📊 Мониторинг: ВЫКЛ';
    btnToggle.className = `btn btn-${state.monitorEnabled ? 'outline' : 'primary'}`;
  }
}
