import { FileText, Settings, LogOut, Map } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const NAV_ITEMS = [
  { to: '/prompt',  label: 'System Prompt', Icon: FileText },
  { to: '/config',  label: 'Cấu hình AI',   Icon: Settings },
  { to: '/scenes',  label: 'Scenes',         Icon: Map },
] as const;

export default function Sidebar() {
  const { logout } = useAuth();

  return (
    <aside className="flex w-56 flex-shrink-0 flex-col border-r border-white/[0.08] bg-surface-card">
      {/* Brand */}
      <div className="flex items-center gap-3 border-b border-white/[0.08] px-5 py-4">
        <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-teal-400 to-cyan-400 text-base leading-none">
          🏔️
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-gray-100">VR 360 Admin</p>
          <p className="text-xs text-gray-500">Lâm Đồng</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 px-2 py-3">
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                isActive
                  ? 'bg-teal-400/10 font-medium text-teal-400'
                  : 'text-gray-400 hover:bg-white/5 hover:text-gray-100'
              }`
            }
          >
            <Icon size={15} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer / Logout */}
      <div className="border-t border-white/[0.08] p-2">
        <button
          onClick={logout}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-gray-400 transition-colors hover:bg-white/5 hover:text-gray-100"
        >
          <LogOut size={15} strokeWidth={2} />
          Đăng xuất
        </button>
      </div>
    </aside>
  );
}
