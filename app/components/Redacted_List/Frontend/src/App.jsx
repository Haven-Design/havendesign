import React, { useState } from "react";
import RedactedList from "./RedactedList";

function App() {
  const [data, setData] = useState({
    Emails: [
      { text: "test@example.com", page: 1, color: "red", selected: true },
    ],
    Phones: [
      { text: "123-456-7890", page: 2, color: "green", selected: true },
    ],
  });

  const handleToggle = (category, idx, checked) => {
    setData((prev) => {
      const newData = { ...prev };
      if (idx === null) {
        newData[category] = newData[category].map((p) => ({
          ...p,
          selected: checked,
        }));
      } else {
        newData[category][idx].selected = checked;
      }
      return newData;
    });
  };

  return (
    <div>
      <h1>Redacted Phrases</h1>
      <RedactedList data={data} onToggle={handleToggle} />
    </div>
  );
}

export default App;
