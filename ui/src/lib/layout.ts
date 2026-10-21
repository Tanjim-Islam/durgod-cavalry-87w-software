// label is the short caption on the cap; name is the unique accessible name.
export interface KeyCap { slot: number; label: string; name: string; x: number; y: number; w: number }

const NAMES: Record<number, { label?: string; name: string }> = {
  79: { label: "Bksp", name: "Backspace" },
  4: { name: "Left Shift" }, 5: { name: "Left Ctrl" }, 17: { name: "Left Alt" },
  82: { name: "Right Shift" }, 53: { name: "Right Alt" }, 83: { name: "Right Ctrl" },
  94: { label: "↑", name: "Up" }, 95: { label: "↓", name: "Down" },
  89: { label: "←", name: "Left" }, 101: { label: "→", name: "Right" },
};

type Row = (string | number)[];
// Each entry: "Label:slot[:width]" or a number = horizontal gap in key units.
const ROWS: Row[] = [
  ["Esc:0", 1, "F1:12", "F2:18", "F3:24", "F4:30", 0.5, "F5:36", "F6:42", "F7:48", "F8:54", 0.5,
   "F9:60", "F10:66", "F11:72", "F12:78", 0.25, "PrtSc:84", "ScrLk:90", "Pause:96"],
  ["`:1", "1:7", "2:13", "3:19", "4:25", "5:31", "6:37", "7:43", "8:49", "9:55", "0:61", "-:67",
   "=:73", "Backspace:79:2", 0.25, "Ins:85", "Home:91", "PgUp:97"],
  ["Tab:2:1.5", "Q:8", "W:14", "E:20", "R:26", "T:32", "Y:38", "U:44", "I:50", "O:56", "P:62",
   "[:68", "]:74", "\\:80:1.5", 0.25, "Del:86", "End:92", "PgDn:98"],
  ["Caps:3:1.75", "A:9", "S:15", "D:21", "F:27", "G:33", "H:39", "J:45", "K:51", "L:57", ";:63",
   "':69", "Enter:81:2.25"],
  ["Shift:4:2.25", "Z:10", "X:16", "C:22", "V:28", "B:34", "N:40", "M:46", ",:52", ".:58", "/:64",
   "Shift :82:2.75", 1.25, "Up:94"],
  ["Ctrl:5:1.25", "Win:11:1.25", "Alt:17:1.25", "Space:35:6.25", "Alt :53:1.25", "Fn:59:1.25",
   "Menu:65:1.25", "Ctrl :83:1.25", 0.25, "Left:89", "Down:95", "Right:101"],
];

// The Fn key is locked on the base layer and on the WASD swap, which overlays it.
export const FN_SLOT = 59;
export const FN_LAYERS: number[] = [0, 3];

export const KEYS: KeyCap[] = ROWS.flatMap((row, r) => {
  let x = 0;
  const y = r === 0 ? 0 : r + 0.25;
  return row.flatMap((e) => {
    if (typeof e === "number") { x += e; return []; }
    const m = e.match(/^(.*?):(\d+)(?::([\d.]+))?$/)!;
    const slot = Number(m[2]);
    const text = m[1].trimEnd() || m[1];
    const cap = { label: NAMES[slot]?.label ?? text, name: NAMES[slot]?.name ?? text, slot, x, y,
                  w: Number(m[3] ?? 1) };
    x += cap.w;
    return [cap];
  });
});
export const KB_WIDTH = Math.max(...KEYS.map((k) => k.x + k.w));
export const KB_HEIGHT = 6.25;
