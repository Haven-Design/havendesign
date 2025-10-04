import React, { useState } from "react";
import "./RedactedList.css";

export default function RedactedList({ hits, onSelectionChange }) {
  const [expanded, setExpanded] = useState({});
  const [selected, setSelected] = useState(() =>
    hits.reduce((acc, h) => {
      acc[h.id] = true;
      return acc;
    }, {})
  );

  const categories = [...new Set(hits.map(h => h.category))];

  const toggleCategory = (cat) => {
    const catHits = hits.filter(h => h.category === cat);
    const allSelected = catHits.every(h => selected[h.id]);
    const newSelected = { ...selected };
    catHits.forEach(h => {
      newSelected[h.id] = !allSelected;
    });
    setSelected(newSelected);
    onSelectionChange(newSelected);
  };

  const toggleHit = (id) => {
    const newSelected = { ...selected, [id]: !selected[id] };
    setSelected(newSelected);
    onSelectionChange(newSelected);
  };

  return (
    <div className="redacted-list-container">
      {categories.map(cat => (
        <div key={cat} className="category">
          <div className="category-header">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={hits.filter(h => h.category === cat).every(h => selected[h.id])}
                onChange={() => toggleCategory(cat)}
              />
              <span className={`category-title category-${cat.toLowerCase()}`}>
                {cat}
              </span>
            </label>
            <button
              className={`collapse-toggle ${expanded[cat] ? "expanded" : ""}`}
              onClick={() => setExpanded({ ...expanded, [cat]: !expanded[cat] })}
            >
              <div className="toggle-knob" />
            </button>
          </div>
          {expanded[cat] !== false && (
            <ul className="hit-list">
              {hits
                .filter(h => h.category === cat)
                .map(h => (
                  <li key={h.id}>
                    <label>
                      <input
                        type="checkbox"
                        checked={selected[h.id]}
                        onChange={() => toggleHit(h.id)}
                      />
                      <span className="hit-phrase">
                        {h.phrase} (p.{h.page})
                      </span>
                    </label>
                  </li>
                ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
