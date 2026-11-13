"""Mon Launcher - tous tes jeux au même endroit (Windows)."""
import colorsys, glob, hashlib, json, os, re, shlex, subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

DATA_DIR = os.path.join(os.path.expanduser("~"), ".mon_launcher")
DATA_FILE = os.path.join(DATA_DIR, "games.json")

BG = "#0e1016"
CARD = "#171a23"
CARD_HOVER = "#1d212c"
TEXT = "#eef0f6"
MUTED = "#7d8398"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#6a4be6"
CARD_W = 210


# ---------- stockage ----------
def load_games():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_games(games):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=2)


# ---------- lancement ----------
def launch(game):
    target, args = game["target"], game.get("args", "")
    try:
        if "://" in target:
            os.startfile(target)
        else:
            cmd = [target] + (shlex.split(args, posix=False) if args else [])
            subprocess.Popen(cmd, cwd=os.path.dirname(target) or None)
    except Exception as e:
        messagebox.showerror("Erreur", f"Impossible de lancer {game['name']} :\n{e}")


# ---------- imports automatiques ----------
def steam_root():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return winreg.QueryValueEx(k, "SteamPath")[0].replace("/", "\\")
    except Exception:
        return r"C:\Program Files (x86)\Steam"


def scan_steam():
    root = steam_root()
    libs = {os.path.join(root, "steamapps")}
    vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
    if os.path.exists(vdf):
        with open(vdf, encoding="utf-8", errors="ignore") as f:
            for p in re.findall(r'"path"\s+"([^"]+)"', f.read()):
                libs.add(os.path.join(p.replace("\\\\", "\\"), "steamapps"))
    found = []
    for lib in libs:
        for acf in glob.glob(os.path.join(lib, "appmanifest_*.acf")):
            try:
                txt = open(acf, encoding="utf-8", errors="ignore").read()
                appid = re.search(r'"appid"\s+"(\d+)"', txt).group(1)
                name = re.search(r'"name"\s+"([^"]+)"', txt).group(1)
            except Exception:
                continue
            if re.search(r"Steamworks|Proton|Steam Linux Runtime", name):
                continue
            found.append({"name": name, "target": f"steam://rungameid/{appid}", "type": "Steam"})
    return found


def scan_epic():
    found = []
    for item in glob.glob(r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item"):
        try:
            d = json.load(open(item, encoding="utf-8"))
            uri = (f"com.epicgames.launcher://apps/{d['CatalogNamespace']}%3A"
                   f"{d['CatalogItemId']}%3A{d['AppName']}?action=launch&silent=true")
            found.append({"name": d["DisplayName"], "target": uri, "type": "Epic"})
        except Exception:
            continue
    return found


def valorant_entry():
    path = r"C:\Riot Games\Riot Client\RiotClientServices.exe"
    if not os.path.exists(path):
        path = filedialog.askopenfilename(title="Trouve RiotClientServices.exe",
                                          filetypes=[("Exécutable", "*.exe")])
        if not path:
            return None
    return {"name": "Valorant", "target": path, "type": "Riot",
            "args": "--launch-product=valorant --launch-patchline=live"}


# ---------- couleurs ----------
def game_colors(name):
    h = int(hashlib.md5(name.encode()).hexdigest()[:4], 16) % 360 / 360

    def hexa(s, v):
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))

    return hexa(0.55, 0.42), hexa(0.30, 0.95)


# ---------- interface ----------
class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=BG)
        ctk.set_appearance_mode("dark")
        self.title("Mon Launcher")
        self.geometry("980x640")
        self.minsize(520, 420)
        self.games = load_games()
        self.cards = []
        self._resize_job = None

        # En-tête
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=28, pady=(24, 8))
        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Ma bibliothèque", text_color=TEXT,
                     font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
        self.count = ctk.CTkLabel(titles, text="", text_color=MUTED, font=ctk.CTkFont(size=13))
        self.count.pack(anchor="w")

        self.add_btn = ctk.CTkButton(head, text="+  Ajouter", width=120, height=40, corner_radius=12,
                                     fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                     font=ctk.CTkFont(size=14, weight="bold"), command=self.open_menu)
        self.add_btn.pack(side="right")
        self.search = ctk.CTkEntry(head, placeholder_text="Rechercher un jeu…", width=260, height=40,
                                   corner_radius=12, fg_color=CARD, border_width=0, text_color=TEXT)
        self.search.pack(side="right", padx=12)
        self.search.bind("<KeyRelease>", lambda e: self.render())

        # Grille
        self.grid_area = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.grid_area.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self.bind("<Configure>", self.on_resize)

        # Menu d'ajout
        self.menu = tk.Menu(self, tearoff=0, bg=CARD, fg=TEXT, activebackground=ACCENT,
                            activeforeground="white", bd=0, font=("Segoe UI", 10))
        self.menu.add_command(label="Importer Steam et Epic", command=self.import_all)
        self.menu.add_command(label="Ajouter Valorant", command=self.add_valorant)
        self.menu.add_command(label="Ajouter un jeu (.exe)", command=self.add_exe)

        self.render()

    # --- affichage ---
    def render(self):
        for c in self.cards:
            c.destroy()
        self.cards = []
        for w in self.grid_area.winfo_children():
            w.destroy()

        term = self.search.get().strip().lower()
        shown = sorted((g for g in self.games if term in g["name"].lower()),
                       key=lambda g: g["name"].lower())
        n = len(self.games)
        self.count.configure(text=f"{n} jeu{'x' if n > 1 else ''}")

        if not shown:
            box = ctk.CTkFrame(self.grid_area, fg_color="transparent")
            box.pack(pady=90)
            msg = "Aucun résultat." if self.games else "Ta bibliothèque est vide."
            ctk.CTkLabel(box, text=msg, text_color=TEXT,
                         font=ctk.CTkFont(size=20, weight="bold")).pack()
            if not self.games:
                ctk.CTkLabel(box, text="Importe tes jeux Steam et Epic en un clic.",
                             text_color=MUTED).pack(pady=(4, 16))
                ctk.CTkButton(box, text="Importer Steam et Epic", height=42, corner_radius=12,
                              fg_color=ACCENT, hover_color=ACCENT_HOVER,
                              command=self.import_all).pack()
            return

        self.grid_holder = ctk.CTkFrame(self.grid_area, fg_color="transparent")
        self.grid_holder.pack(fill="both", expand=True)
        self.cards = [self.make_card(g) for g in shown]
        self.layout_cards()

    def make_card(self, g):
        card = ctk.CTkFrame(self.grid_holder, width=CARD_W, height=232, corner_radius=18, fg_color=CARD)
        card.grid_propagate(False)
        card.pack_propagate(False)
        dark, light = game_colors(g["name"])

        banner = ctk.CTkFrame(card, height=104, corner_radius=14, fg_color=dark)
        banner.pack(fill="x", padx=8, pady=(8, 0))
        banner.pack_propagate(False)
        letter = (g["name"].strip()[:1] or "?").upper()
        ctk.CTkLabel(banner, text=letter, text_color=light,
                     font=ctk.CTkFont(size=46, weight="bold")).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkButton(banner, text="✕", width=24, height=24, corner_radius=12, fg_color="transparent",
                      hover_color="#c0392b", text_color=light, font=ctk.CTkFont(size=11),
                      command=lambda: self.remove(g)).place(relx=1.0, x=-6, y=6, anchor="ne")

        ctk.CTkLabel(card, text=g["name"], text_color=TEXT, anchor="w", justify="left",
                     wraplength=CARD_W - 30, font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(card, text=g.get("type", "Autre"), text_color=MUTED, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x", padx=14)
        ctk.CTkButton(card, text="▶  Jouer", height=34, corner_radius=10, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, font=ctk.CTkFont(size=13, weight="bold"),
                      command=lambda: launch(g)).pack(side="bottom", fill="x", padx=12, pady=12)
        return card

    def layout_cards(self):
        if not self.cards:
            return
        width = max(self.grid_area.winfo_width(), self.winfo_width() - 60)
        cols = max(1, width // (CARD_W + 16))
        for c in self.cards:
            c.grid_forget()
        for i, c in enumerate(self.cards):
            c.grid(row=i // cols, column=i % cols, padx=8, pady=8, sticky="n")

    def on_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, self.layout_cards)

    # --- actions ---
    def open_menu(self):
        x = self.add_btn.winfo_rootx()
        y = self.add_btn.winfo_rooty() + self.add_btn.winfo_height() + 4
        self.menu.tk_popup(x, y)

    def add(self, new):
        known = {g["name"].lower() for g in self.games}
        added = [g for g in new if g["name"].lower() not in known]
        self.games.extend(added)
        save_games(self.games)
        self.render()
        return len(added)

    def add_exe(self):
        path = filedialog.askopenfilename(filetypes=[("Exécutable", "*.exe"), ("Tous", "*.*")])
        if not path:
            return
        default = os.path.splitext(os.path.basename(path))[0]
        name = simpledialog.askstring("Nom du jeu", "Nom :", initialvalue=default, parent=self)
        if name:
            self.add([{"name": name, "target": path, "type": "Exe"}])

    def add_valorant(self):
        e = valorant_entry()
        if e:
            self.add([e])

    def import_all(self):
        n = self.add(scan_steam() + scan_epic())
        messagebox.showinfo("Import", f"{n} jeu(x) ajouté(s).")

    def remove(self, g):
        if messagebox.askyesno("Retirer", f"Retirer {g['name']} du launcher ?"):
            self.games.remove(g)
            save_games(self.games)
            self.render()


if __name__ == "__main__":
    App().mainloop()
