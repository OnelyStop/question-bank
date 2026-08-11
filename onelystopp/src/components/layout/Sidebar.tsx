import { MessageSquarePlus } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useApp } from "../../context/AppContext";
import { NAV_GROUPS } from "../../data/navigation";
import { Badge } from "../ui/Badge";
import { NavIcon } from "../ui/NavIcon";
import "./Sidebar.css";

export function Sidebar() {
  const { markerLabel } = useApp();

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo" aria-hidden>
          <span />
          <span />
        </div>
        <span className="sidebar__name">onelystopp</span>
      </div>

      <nav className="sidebar__nav">
        {NAV_GROUPS.map((group) => (
          <div key={group.id} className="sidebar__group">
            <div className="sidebar__group-label">{group.label}</div>
            <ul className="sidebar__list">
              {group.items.map((item) => {
                const label = item.dynamicLabel ? markerLabel : item.label;
                return (
                  <li key={item.id}>
                    <NavLink
                      to={item.path}
                      end={item.path === "/"}
                      className={({ isActive }) =>
                        `sidebar__link ${isActive ? "sidebar__link--active" : ""}`
                      }
                    >
                      <NavIcon name={item.icon} />
                      <span className="sidebar__link-text">{label}</span>
                      {item.badge === "NEW" && <Badge>New</Badge>}
                      {item.badge === "BETA" && <Badge tone="grey">Beta</Badge>}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="sidebar__footer">
        <button type="button" className="sidebar__feedback">
          <MessageSquarePlus size={16} strokeWidth={1.75} />
          Leave feedback
        </button>
      </div>
    </aside>
  );
}
