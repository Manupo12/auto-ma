import { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  sublabel?: string;
  icon?: LucideIcon;
  onClick?: () => void;
  href?: string;
  color?: "azul" | "verde" | "rojo" | "amarillo";
  disabled?: boolean;
  loading?: boolean;
}

const COLORS = {
  azul: "bg-blue-600 hover:bg-blue-700 text-white",
  verde: "bg-green-600 hover:bg-green-700 text-white",
  rojo: "bg-red-600 hover:bg-red-700 text-white",
  amarillo: "bg-amber-500 hover:bg-amber-600 text-white",
};

export function BotonGigante({ label, sublabel, icon: Icon, onClick, href, color = "azul", disabled, loading }: Props) {
  const className = `flex items-center justify-center gap-4 px-8 py-6 rounded-2xl shadow-md transition-all ${COLORS[color]} ${disabled || loading ? "opacity-50 cursor-not-allowed" : "active:scale-95"}`;

  const content = (
    <>
      {Icon && <Icon size={32} />}
      <div className="text-left">
        <p className="text-xl font-bold">{loading ? "Procesando..." : label}</p>
        {sublabel && <p className="text-sm opacity-90">{sublabel}</p>}
      </div>
    </>
  );

  if (href && !disabled) {
    return <a href={href} className={className}>{content}</a>;
  }
  return <button onClick={onClick} disabled={disabled || loading} className={className}>{content}</button>;
}
