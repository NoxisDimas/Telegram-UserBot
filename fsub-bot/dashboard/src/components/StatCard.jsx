export default function StatCard({ icon: Icon, title, value, subtitle, trend }) {
  return (
    <div className="card card-hover group relative p-6 transition-all duration-300 overflow-hidden">
      {/* Hover glow overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-neon/[0.03] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none rounded-xl" />

      <div className="relative z-10">
        {/* Top row: icon + trend */}
        <div className="flex items-center justify-between mb-5">
          <div className="w-11 h-11 rounded-xl bg-neon/8 border border-neon/20 flex items-center justify-center">
            {Icon && <Icon className="w-5 h-5 text-neon" strokeWidth={1.8} />}
          </div>
          {trend !== undefined && trend !== null && (
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-lg ${
              trend > 0
                ? 'bg-neon/8 text-neon'
                : trend < 0
                  ? 'bg-danger/10 text-danger'
                  : 'bg-bg-card-hover text-text-muted'
            }`}>
              {trend > 0 ? '+' : ''}{trend}%
            </span>
          )}
        </div>

        {/* Title */}
        <p className="text-text-muted text-[11px] font-semibold uppercase tracking-wider mb-2">{title}</p>

        {/* Value */}
        <p className="text-3xl font-bold text-text-primary tracking-tight leading-none">{value}</p>

        {/* Subtitle */}
        {subtitle && (
          <p className="text-text-muted text-xs mt-2.5">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
