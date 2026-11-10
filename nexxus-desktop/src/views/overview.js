// Панель Overview: рендер поверх guardian_status_cmd.
import { formatUptime, statusClass } from '../format.js';

export const OVERVIEW_TAB = 'overview';

/// Заполняет плашки overview из state (см. fetchStatus в main.js).
export function render(root, state) {
  const set = (id, text) => {
    const el = root.getElementById(id);
    if (el) el.textContent = text;
  };
  // Node ID вынесен в широкое поле над вкладками.
  set('node-id-value', state.nodeId);
  set('guardian-state', state.guardianState);
  set('guardian-api', state.apiReachable ? 'Доступен' : 'Недоступен');
  set('guardian-uptime', formatUptime(state.uptimeMs));
  set('guardian-peers', state.peers);
  set('guardian-chunks', state.chunks);
  set('guardian-epoch', state.epoch);
  set('guardian-tor', state.tor);
  set('guardian-tg', state.tgConfigured ? 'Настроен' : 'Не настроен');

  const stateEl = root.getElementById('guardian-state');
  if (stateEl) {
    stateEl.className = `guardian-stat-value ${statusClass(state.guardianState)}`;
  }
  const apiEl = root.getElementById('guardian-api');
  if (apiEl) {
    apiEl.className = `guardian-stat-value ${state.apiReachable ? 'status-running' : 'status-unhealthy'}`;
  }

  const btnToggle = root.getElementById('btn-toggle-monitor');
  if (btnToggle) {
    btnToggle.textContent = state.monitorEnabled ? '📊 Мониторинг: ВКЛ' : '📊 Мониторинг: ВЫКЛ';
    btnToggle.className = `btn btn-${state.monitorEnabled ? 'outline' : 'primary'}`;
  }
}
