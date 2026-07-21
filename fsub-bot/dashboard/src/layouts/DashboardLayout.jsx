import { useState, useEffect } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Radio,
  FileText,
  Megaphone,
  UserCog,
  LogOut,
  PanelLeftClose,
  PanelLeft,
  Menu,
  Bot,
} from 'lucide-react';

const navItems = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/fsub', label: 'FSUB Channels', icon: Radio },
  { path: '/content', label: 'Content', icon: FileText },
  { path: '/broadcast', label: 'Broadcast', icon: Megaphone },
  { path: '/users', label: 'Settings', icon: UserCog },
];

export default function DashboardLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const NavLink = ({ path, label, icon: Icon }) => {
    const active = isActive(path);
    return (
      <Link
        to={path}
        title={collapsed ? label : undefined}
        className={`
          flex items-center gap-3 rounded-lg transition-all duration-200
          ${collapsed ? 'justify-center p-2.5' : 'px-3 py-2.5'}
          ${active
            ? 'bg-neon/10 text-neon neon-glow-sm'
            : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
          }
        `}
      >
        <Icon className="w-5 h-5 flex-shrink-0" strokeWidth={active ? 2.2 : 1.8} />
        {!collapsed && <span className="text-[13px] font-medium truncate">{label}</span>}
      </Link>
    );
  };

  const SidebarInner = () => (
    <div className="flex flex-col h-full">
      {/* Brand */}
      <div className={`flex items-center gap-3 h-16 border-b border-border flex-shrink-0 ${collapsed ? 'justify-center px-3' : 'px-5'}`}>
        <div className="w-9 h-9 rounded-lg bg-neon/8 border border-neon/20 flex items-center justify-center flex-shrink-0">
          <Bot className="w-5 h-5 text-neon" />
        </div>
        {!collapsed && (
          <div>
            <h1 className="text-sm font-bold text-text-primary leading-tight">Fsub Bot</h1>
            <p className="text-[10px] text-text-muted leading-tight mt-0.5">Dashboard</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto px-3 pt-6 pb-4">
        {!collapsed && (
          <p className="px-3 mb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted">
            Menu
          </p>
        )}
        <nav className="space-y-1.5">
          {navItems.map((item) => (
            <NavLink key={item.path} {...item} />
          ))}
        </nav>
      </div>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-border flex-shrink-0 space-y-1.5">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={`hidden lg:flex items-center gap-3 w-full rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-card transition-all text-[13px] ${collapsed ? 'justify-center p-2.5' : 'px-3 py-2.5'}`}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeft className="w-5 h-5" />
          ) : (
            <><PanelLeftClose className="w-5 h-5 flex-shrink-0" /><span className="font-medium">Collapse</span></>
          )}
        </button>
        <button
          onClick={handleLogout}
          title={collapsed ? 'Logout' : undefined}
          className={`flex items-center gap-3 w-full rounded-lg text-[13px] font-medium text-text-muted hover:bg-danger/8 hover:text-danger transition-all duration-200 ${collapsed ? 'justify-center p-2.5' : 'px-3 py-2.5'}`}
        >
          <LogOut className="w-5 h-5 flex-shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary">
      {/* Desktop Sidebar */}
      <aside className={`hidden lg:block bg-bg-secondary border-r border-border flex-shrink-0 transition-all duration-300 ease-in-out ${collapsed ? 'w-[72px]' : 'w-[250px]'}`}>
        <SidebarInner />
      </aside>

      {/* Mobile Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={() => setMobileOpen(false)} />
          <aside className="relative w-[270px] h-full bg-bg-secondary border-r border-border animate-slide-in-left z-10">
            <SidebarInner />
          </aside>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between h-16 px-6 lg:px-8 border-b border-border bg-bg-secondary/80 backdrop-blur-md flex-shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileOpen(true)} className="lg:hidden p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-card transition-colors">
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-sm font-semibold text-text-primary">
              {navItems.find(item => isActive(item.path))?.label || 'Dashboard'}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:block text-right mr-2">
              <p className="text-[13px] font-medium text-text-primary leading-tight">Admin</p>
              <p className="text-[10px] text-text-muted leading-tight">Administrator</p>
            </div>
            <div className="w-9 h-9 rounded-full bg-neon/8 border border-neon/20 flex items-center justify-center">
              <span className="text-xs font-bold text-neon">A</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-6 lg:p-8 animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
