import React, { useState } from "react";
import "./RedactedList.css";

export default function RedactedList({ data, onToggle }) {
  const [collapsed, setCollapsed] = useState({});

  const toggleCollapse = (category) => {
    setCollapsed((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  };

  return (
    <div className="redacted-list">
      {Object.entries(data).map(([category, phrases]) => (
        <div key={category} className="category">
          <div className="category-header">
            <input
              type="checkbox"
              checked={phrases.every((p) => p.selected)}
              onChange={(e) => onToggle(category, null, e.target.checked)}
            />
            <span
              className="category-title"
              style={{ color: phrases[0]?.color || "#000" }}
            >
              {category}
            </span>
            <button
              className="collapse-toggle"
              onClick={() => toggleCollapse(category)}
            >
              {collapsed[category] ? "▶" : "▼"}
            </button>
          </div>
          {!collapsed[category] && (
            <ul className="phrases">
              {phrases.map((p, idx) => (
                <li key={idx}>
                  <input
                    type="checkbox"
                    checked={p.selected}
                    onChange={(e) => onToggle(category, idx, e.target.checked)}
                  />
                  <span style={{ color: p.color }}>{p.text}</span>{" "}
                  <small>(page {p.page})</small>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
