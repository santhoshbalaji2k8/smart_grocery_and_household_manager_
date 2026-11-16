from __future__ import annotations
import sys, csv, shutil, sqlite3, json, calendar, math, logging
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit('CustomTkinter is required. Run: pip install -r requirements.txt')

from database import Database, money, validate_backup

ROOT=Path(__file__).resolve().parent.parent
LOG_DIR=ROOT/'logs'
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=LOG_DIR/'application.log', level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s')
except OSError:
    logging.basicConfig(level=logging.ERROR)

def shopping_estimated_total(items):
    return sum((Decimal(str(item['quantity'])) * money(item['unit_price']) for item in items), Decimal('0.00'))

def spreadsheet_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def format_date_value(value, date_format):
    if value in (None, ''):
        return value or ''
    try:
        return date.fromisoformat(str(value)).strftime(date_format)
    except (TypeError, ValueError):
        return str(value)

def format_datetime_value(value, date_format):
    """Display SQLite UTC timestamps in the computer's local timezone.

    SQLite CURRENT_TIMESTAMP stores UTC as a timezone-naive ISO string. Treat
    naive values as UTC (never as local time), then convert to the operating
    system's configured local timezone for display. Explicit offsets are
    respected. The database value itself is never modified.
    """
    if value in (None, ''):
        return value or ''
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local_value = parsed.astimezone()  # system's local timezone
        try:
            date_part = local_value.strftime(date_format)
        except (TypeError, ValueError):
            date_part = local_value.strftime('%Y-%m-%d')
        return f"{date_part} {local_value.strftime('%H:%M:%S')}"
    except (TypeError, ValueError, OverflowError, OSError):
        # Preserve an unexpected legacy value instead of breaking page render.
        return raw
CURRENCIES={'INR':('₹',2),'USD':('$',2),'EUR':('€',2),'GBP':('£',2),'JPY':('¥',0),'AED':('د.إ',2)}
LANGS={
 'English': {'Dashboard':'Dashboard','Inventory':'Inventory','Purchases':'Orders / Purchases','Household':'Household Members','Reports':'Reports & Analytics','Shopping':'Shopping List','Stores':'Store Price Comparison','Expiry':'Expiry Tracker','Expenses':'Expenses & Budget','Assistant':'Smart Assistant','Notifications':'Notifications','Settings':'Settings','Help':'Help / Support','Logout':'Logout'},
 'Tamil': {'Dashboard':'முகப்பு','Inventory':'சரக்கு','Purchases':'கொள்முதல்கள்','Household':'குடும்ப உறுப்பினர்கள்','Reports':'அறிக்கைகள்','Shopping':'ஷாப்பிங் பட்டியல்','Stores':'கடை விலை ஒப்பீடு','Expiry':'காலாவதி கண்காணிப்பு','Expenses':'செலவுகள் மற்றும் பட்ஜெட்','Assistant':'ஸ்மார்ட் உதவியாளர்','Notifications':'அறிவிப்புகள்','Settings':'அமைப்புகள்','Help':'உதவி','Logout':'வெளியேறு'},
 'Hindi': {'Dashboard':'डैशबोर्ड','Inventory':'इन्वेंटरी','Purchases':'खरीदारी','Household':'परिवार के सदस्य','Reports':'रिपोर्ट और विश्लेषण','Shopping':'खरीदारी सूची','Stores':'दुकान मूल्य तुलना','Expiry':'समाप्ति ट्रैकर','Expenses':'खर्च और बजट','Assistant':'स्मार्ट सहायक','Notifications':'सूचनाएं','Settings':'सेटिंग्स','Help':'सहायता','Logout':'लॉग आउट'},
 'Telugu': {'Dashboard':'డాష్‌బోర్డ్','Inventory':'ఇన్వెంటరీ','Purchases':'కొనుగోళ్లు','Household':'కుటుంబ సభ్యులు','Reports':'నివేదికలు','Shopping':'షాపింగ్ జాబితా','Stores':'దుకాణ ధర పోలిక','Expiry':'గడువు ట్రాకర్','Expenses':'ఖర్చులు మరియు బడ్జెట్','Assistant':'స్మార్ట్ సహాయకుడు','Notifications':'నోటిఫికేషన్లు','Settings':'సెట్టింగ్‌లు','Help':'సహాయం','Logout':'లాగ్ అవుట్'},
 'Kannada': {'Dashboard':'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್','Inventory':'ದಾಸ್ತಾನು','Purchases':'ಖರೀದಿಗಳು','Household':'ಕುಟುಂಬ ಸದಸ್ಯರು','Reports':'ವರದಿಗಳು','Shopping':'ಖರೀದಿ ಪಟ್ಟಿ','Stores':'ಅಂಗಡಿ ಬೆಲೆ ಹೋಲಿಕೆ','Expiry':'ಅವಧಿ ಟ್ರ್ಯಾಕರ್','Expenses':'ವೆಚ್ಚ ಮತ್ತು ಬಜೆಟ್','Assistant':'ಸ್ಮಾರ್ಟ್ ಸಹಾಯಕ','Notifications':'ಅಧಿಸೂಚನೆಗಳು','Settings':'ಸೆಟ್ಟಿಂಗ್‌ಗಳು','Help':'ಸಹಾಯ','Logout':'ಲಾಗ್ ಔಟ್'}
}

UI_TRANSLATIONS = {'Tamil': {'Save': 'சேமி', 'Add Product': 'பொருளைச் சேர்', 'Edit Product': 'பொருளைத் திருத்து', 'Product Name': 'பொருளின் பெயர்', 'Category': 'வகை', 'Brand': 'பிராண்ட்', 'Unit (kg/L/pcs)': 'அலகு (kg/L/pcs)', 'Current Quantity': 'தற்போதைய அளவு', 'Minimum Stock': 'குறைந்தபட்ச இருப்பு', 'Unit Price': 'அலகு விலை', 'Preferred Store': 'விருப்பமான கடை', 'Expiry Date (YYYY-MM-DD)': 'காலாவதி தேதி (YYYY-MM-DD)', 'Application Settings': 'பயன்பாட்டு அமைப்புகள்', 'Appearance': 'தோற்றம்', 'Currency display': 'நாணயக் காட்சி', 'Language': 'மொழி', 'Date format': 'தேதி வடிவம்', 'Create Database Backup': 'தரவுத்தள காப்புப்பிரதி உருவாக்கு', 'Restore Database Backup': 'காப்புப்பிரதியை மீட்டமை', 'Save alert thresholds': 'எச்சரிக்கை வரம்புகளைச் சேமி', 'Product Inventory': 'பொருள் இருப்பு', 'Total Products': 'மொத்த பொருட்கள்', 'Low Stock': 'குறைந்த இருப்பு', 'Out Of Stock': 'இருப்பு இல்லை', 'In Stock': 'இருப்பில் உள்ளது', 'All Products': 'அனைத்து பொருட்கள்', 'Search inventory...': 'இருப்பைத் தேடு', 'Export': 'ஏற்றுமதி'}, 'Hindi': {'Save': 'सहेजें', 'Add Product': 'उत्पाद जोड़ें', 'Edit Product': 'उत्पाद संपादित करें', 'Product Name': 'उत्पाद का नाम', 'Category': 'श्रेणी', 'Brand': 'ब्रांड', 'Unit (kg/L/pcs)': 'इकाई (kg/L/pcs)', 'Current Quantity': 'वर्तमान मात्रा', 'Minimum Stock': 'न्यूनतम स्टॉक', 'Unit Price': 'प्रति इकाई मूल्य', 'Preferred Store': 'पसंदीदा दुकान', 'Expiry Date (YYYY-MM-DD)': 'समाप्ति तिथि (YYYY-MM-DD)', 'Application Settings': 'ऐप सेटिंग्स', 'Appearance': 'दिखावट', 'Currency display': 'मुद्रा प्रदर्शन', 'Language': 'भाषा', 'Date format': 'दिनांक प्रारूप', 'Create Database Backup': 'डेटाबेस बैकअप बनाएं', 'Restore Database Backup': 'बैकअप पुनर्स्थापित करें', 'Save alert thresholds': 'अलर्ट सीमाएं सहेजें', 'Product Inventory': 'उत्पाद सूची', 'Total Products': 'कुल उत्पाद', 'Low Stock': 'कम स्टॉक', 'Out Of Stock': 'स्टॉक समाप्त', 'In Stock': 'स्टॉक में', 'All Products': 'सभी उत्पाद', 'Search inventory...': 'इन्वेंटरी खोजें', 'Export': 'निर्यात'}, 'Telugu': {'Save': 'సేవ్ చేయి', 'Add Product': 'ఉత్పత్తిని జోడించు', 'Edit Product': 'ఉత్పత్తిని సవరించు', 'Product Name': 'ఉత్పత్తి పేరు', 'Category': 'వర్గం', 'Brand': 'బ్రాండ్', 'Unit (kg/L/pcs)': 'యూనిట్ (kg/L/pcs)', 'Current Quantity': 'ప్రస్తుత పరిమాణం', 'Minimum Stock': 'కనీస నిల్వ', 'Unit Price': 'యూనిట్ ధర', 'Preferred Store': 'ఇష్టమైన దుకాణం', 'Expiry Date (YYYY-MM-DD)': 'గడువు తేదీ (YYYY-MM-DD)', 'Application Settings': 'అప్లికేషన్ సెట్టింగ్\u200cలు', 'Appearance': 'రూపం', 'Currency display': 'కరెన్సీ ప్రదర్శన', 'Language': 'భాష', 'Date format': 'తేదీ ఆకృతి', 'Create Database Backup': 'డేటాబేస్ బ్యాకప్ సృష్టించు', 'Restore Database Backup': 'బ్యాకప్ పునరుద్ధరించు', 'Save alert thresholds': 'హెచ్చరిక పరిమితులను సేవ్ చేయి', 'Product Inventory': 'ఉత్పత్తి నిల్వ', 'Total Products': 'మొత్తం ఉత్పత్తులు', 'Low Stock': 'తక్కువ నిల్వ', 'Out Of Stock': 'నిల్వ లేదు', 'In Stock': 'నిల్వలో ఉంది', 'All Products': 'అన్ని ఉత్పత్తులు', 'Search inventory...': 'నిల్వను వెతుకు', 'Export': 'ఎగుమతి'}, 'Kannada': {'Save': 'ಉಳಿಸಿ', 'Add Product': 'ಉತ್ಪನ್ನ ಸೇರಿಸಿ', 'Edit Product': 'ಉತ್ಪನ್ನ ಸಂಪಾದಿಸಿ', 'Product Name': 'ಉತ್ಪನ್ನದ ಹೆಸರು', 'Category': 'ವರ್ಗ', 'Brand': 'ಬ್ರ್ಯಾಂಡ್', 'Unit (kg/L/pcs)': 'ಘಟಕ (kg/L/pcs)', 'Current Quantity': 'ಪ್ರಸ್ತುತ ಪ್ರಮಾಣ', 'Minimum Stock': 'ಕನಿಷ್ಠ ಸಂಗ್ರಹ', 'Unit Price': 'ಘಟಕದ ಬೆಲೆ', 'Preferred Store': 'ಆದ್ಯತೆಯ ಅಂಗಡಿ', 'Expiry Date (YYYY-MM-DD)': 'ಮುಕ್ತಾಯ ದಿನಾಂಕ (YYYY-MM-DD)', 'Application Settings': 'ಅಪ್ಲಿಕೇಶನ್ ಸೆಟ್ಟಿಂಗ್\u200cಗಳು', 'Appearance': 'ರೂಪ', 'Currency display': 'ಕರೆನ್ಸಿ ಪ್ರದರ್ಶನ', 'Language': 'ಭಾಷೆ', 'Date format': 'ದಿನಾಂಕ ಸ್ವರೂಪ', 'Create Database Backup': 'ಡೇಟಾಬೇಸ್ ಬ್ಯಾಕಪ್ ರಚಿಸಿ', 'Restore Database Backup': 'ಬ್ಯಾಕಪ್ ಮರುಸ್ಥಾಪಿಸಿ', 'Save alert thresholds': 'ಎಚ್ಚರಿಕೆ ಮಿತಿಗಳನ್ನು ಉಳಿಸಿ', 'Product Inventory': 'ಉತ್ಪನ್ನ ಸಂಗ್ರಹ', 'Total Products': 'ಒಟ್ಟು ಉತ್ಪನ್ನಗಳು', 'Low Stock': 'ಕಡಿಮೆ ಸಂಗ್ರಹ', 'Out Of Stock': 'ಸಂಗ್ರಹ ಇಲ್ಲ', 'In Stock': 'ಸಂಗ್ರಹದಲ್ಲಿದೆ', 'All Products': 'ಎಲ್ಲಾ ಉತ್ಪನ್ನಗಳು', 'Search inventory...': 'ಸಂಗ್ರಹ ಹುಡುಕಿ', 'Export': 'ರಫ್ತು'}}


class SpreadsheetGridTable:
    """Scrollable, spreadsheet-style table with real bordered cells.

    Keeps the small selection API used by existing edit/delete actions so the
    rest of the application does not need to change.
    """
    def __init__(self, parent, columns, rows, app, height=12):
        self.app = app
        self.columns = list(columns)
        self.rows = {}
        self.selected = None
        self.callbacks = {}
        self.frame = tk.Frame(parent, bg=app.colors['border'], bd=1, relief='solid')
        self.frame.pack(fill='both', expand=True, pady=5)
        self.canvas = tk.Canvas(self.frame, bg=app.colors['card'], highlightthickness=0, height=max(150, height * 34))
        self.vbar = ttk.Scrollbar(self.frame, orient='vertical', command=self.canvas.yview)
        self.hbar = ttk.Scrollbar(self.frame, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.vbar.pack(side='right', fill='y')
        self.hbar.pack(side='bottom', fill='x')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.inner = tk.Frame(self.canvas, bg=app.colors['border'])
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', self._update_scrollregion)
        self.canvas.bind('<Configure>', self._resize_inner)
        self._cell_widgets = {}
        self._build(rows)

    def _update_scrollregion(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _resize_inner(self, event):
        # Keep columns spread across the available width, but allow horizontal
        # scrolling when there are many columns.
        minimum = max(150, len(self.columns) * 132)
        width = max(event.width, minimum)
        self.canvas.itemconfigure(self.window_id, width=width)
        cell_width = max(132, width // max(1, len(self.columns)))
        for widget in self._cell_widgets.values():
            widget.configure(wraplength=max(90, cell_width - 18))
        self._update_scrollregion()

    def _build(self, rows):
        count = max(1, len(self.columns))
        for col_index, column in enumerate(self.columns):
            self.inner.grid_columnconfigure(col_index, weight=1, uniform='spreadsheet_columns')
            header = tk.Label(self.inner, text=self.app.tr(str(column)), bg=self.app.colors['main'],
                              fg=self.app.colors['text'], font=('Segoe UI', 10, 'bold'),
                              anchor='center', justify='center', padx=7, pady=9,
                              bd=1, relief='solid', highlightthickness=0)
            header.grid(row=0, column=col_index, sticky='nsew')
        date_columns = {'date','purchase_date','expense_date','list_date','recorded_date','next_due',
                        'last_generated','expiry_date','waste_date','start_date','end_date'}
        datetime_columns = {'created_at', 'updated_at'}
        for row_index, row in enumerate(rows, start=1):
            iid = str(row_index)
            raw_id = row.get('_id', row.get('id', ''))
            stripe = row_index % 2 == 0
            bg = ('#354654' if self.app.theme == 'Dark' else '#F1F5F9') if stripe else self.app.colors['card']
            self.rows[iid] = {'tags': (str(raw_id), 'row_even' if not stripe else 'row_odd')}
            for col_index, column in enumerate(self.columns):
                value = row.get(column, '')
                if column in datetime_columns and value not in (None, ''):
                    value = format_datetime_value(value, self.app.date_format)
                elif column in date_columns and value not in (None, ''):
                    value = self.app.format_date(value)
                text = '' if value is None else str(value)
                cell = tk.Label(self.inner, text=text, bg=bg, fg=self.app.colors['text'],
                                font=('Segoe UI', 9), anchor='center', justify='center',
                                padx=8, pady=9, bd=1, relief='solid', highlightthickness=0)
                cell.grid(row=row_index, column=col_index, sticky='nsew')
                self._cell_widgets[(row_index, col_index)] = cell
                cell.bind('<Button-1>', lambda event, item=iid: self.selection_set(item))
                cell.bind('<Button-3>', lambda event, item=iid: self._right_click(event, item))
                cell.bind('<Double-1>', lambda event, item=iid: self._double_click(event, item))
        self._update_scrollregion()

    def _right_click(self, event, iid):
        self.selection_set(iid)
        callback = self.callbacks.get('<Button-3>')
        if callback:
            return callback(event)

    def _double_click(self, event, iid):
        self.selection_set(iid)
        callback = self.callbacks.get('<Double-1>')
        if callback:
            return callback(event)

    def bind(self, sequence, callback, add=None):
        self.callbacks[sequence] = callback
        return None

    def selection(self):
        return (self.selected,) if self.selected else ()

    def selection_set(self, iid):
        iid = str(iid)
        if iid in self.rows:
            self.selected = iid
            for (row, _col), widget in self._cell_widgets.items():
                if row == int(iid):
                    widget.configure(relief='solid', bd=2, bg=self.app.colors['green'], fg='#FFFFFF')
                else:
                    original = ('#354654' if self.app.theme == 'Dark' else '#F1F5F9') if row % 2 == 0 else self.app.colors['card']
                    widget.configure(relief='solid', bd=1, bg=original, fg=self.app.colors['text'])

    def item(self, iid, option=None):
        data = self.rows.get(str(iid), {})
        return data.get(option, data) if option else data

    def identify_row(self, _y):
        return self.selected or ''

class GroceryApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.db=Database(); self.db.generate_notifications()
        self.title('Smart Grocery & Household Manager'); self.geometry('1440x900'); self.minsize(1120,720)
        self.page='Inventory'; self.theme=self.db.setting('theme','Light'); self.currency=self.db.setting('currency','INR'); self.language=self.db.setting('language','English'); self.date_format=self.db.setting('date_format','%d-%m-%Y')
        self.colors={}
        self.apply_theme(first=True)
        self.grid_columnconfigure(1,weight=1); self.grid_rowconfigure(0,weight=1)
        self.sidebar=ctk.CTkFrame(self,width=205,corner_radius=22,fg_color=self.colors['sidebar']); self.sidebar.grid(row=0,column=0,padx=(18,8),pady=18,sticky='nsew'); self.sidebar.grid_propagate(False)
        self.main=ctk.CTkFrame(self,corner_radius=22,fg_color=self.colors['main']); self.configure(fg_color=self.colors['outer']); self.main.grid(row=0,column=1,padx=(8,18),pady=18,sticky='nsew'); self.main.grid_columnconfigure(0,weight=1); self.main.grid_rowconfigure(1,weight=1)
        self.build_sidebar(); self.build_header(); self.show_page('Inventory')
        self.bind('<Control-f>',lambda e:self.focus_search()); self.bind('<Control-n>',lambda e:self.open_add_for_page())

    def report_callback_exception(self, exc, value, tb):
        logging.error('Unhandled interface callback exception', exc_info=(exc, value, tb))
        try:
            messagebox.showerror('Unexpected application error', f'{value}\n\nIf the project folder is writable, details are in logs/application.log. Keep the IDLE Shell open for additional diagnostics.')
        except Exception:
            pass

    def apply_theme(self,first=False):
        dark=self.theme=='Dark'
        # Destroy old CTkScrollableFrame canvases and their Tcl callbacks BEFORE
        # changing the global appearance mode. Changing mode first can trigger
        # configure callbacks on a canvas that is already being torn down
        # (invalid command name ...ctkcanvas on Windows/Tk 8.6).
        has_shell = hasattr(self, 'sidebar') and hasattr(self, 'main')
        if has_shell:
            for widget in list(self.main.winfo_children()):
                try: widget.destroy()
                except tk.TclError: pass
            for widget in list(self.sidebar.winfo_children()):
                try: widget.destroy()
                except tk.TclError: pass
        ctk.set_appearance_mode('Dark' if dark else 'Light')
        ctk.set_default_color_theme('green')
        self.colors={'outer':'#202B36' if dark else '#DCE5EC','sidebar':'#222E39' if dark else '#FFFFFF','main':'#263442' if dark else '#F1F6FC','card':'#303F4D' if dark else '#FFFFFF','text':'#F0F4F7' if dark else '#202A32','muted':'#B0BEC9' if dark else '#718096','green':'#16A36A','green_light':'#174D3C' if dark else '#E9F8F1','border':'#43515D' if dark else '#E8EDF2','red':'#E36B6B','orange':'#E8A23A'}
        if has_shell:
            self.configure(fg_color=self.colors['outer'])
            self.sidebar.configure(fg_color=self.colors['sidebar'])
            self.main.configure(fg_color=self.colors['main'])
            self.show_page(self.page)
    def tr(self,key):
        language = getattr(self, 'language', 'English')
        return LANGS.get(language, LANGS['English']).get(key, UI_TRANSLATIONS.get(language, {}).get(key, key))
    def format_date(self,value):
        return format_date_value(value, self.date_format)
    def fmt(self,value):
        symbol,dec=CURRENCIES.get(self.currency,('₹',2))
        try:
            number=float(value)
            if not math.isfinite(number): raise ValueError('Non-finite amount')
            return f"{symbol}{number:,.{dec}f}"
        except (ValueError,TypeError,OverflowError):
            return f'{symbol}{0:.{dec}f}'
    def card(self,parent,**kw): return ctk.CTkFrame(parent,corner_radius=15,fg_color=self.colors['card'],border_width=1,border_color=self.colors['border'],**kw)
    def label(self,parent,text,size=13,weight='normal',color=None,**kw): return ctk.CTkLabel(parent,text=self.tr(str(text)),font=ctk.CTkFont(size=size,weight=weight),text_color=color or self.colors['text'],**kw)
    def button(self,parent,text,command,primary=False,**kw): return ctk.CTkButton(parent,text=self.tr(str(text)),command=command,height=34,corner_radius=10,fg_color=self.colors['green'] if primary else self.colors['card'],hover_color='#0E8758' if primary else self.colors['border'],text_color='#FFFFFF' if primary else self.colors['text'],border_width=0 if primary else 1,border_color=self.colors['border'],**kw)
    def build_sidebar(self):
        for w in self.sidebar.winfo_children(): w.destroy()
        brand=ctk.CTkFrame(self.sidebar,fg_color='transparent'); brand.pack(fill='x',padx=14,pady=(18,20))
        self.label(brand,'🛒  FreshCart',20,'bold',self.colors['green']).pack(anchor='w')
        groups=[('MAIN',['Dashboard','Purchases','Inventory','Household','Reports']),('TOOLS',['Shopping','Stores','Expiry','Expenses','Assistant']),('OTHER',['Notifications','Settings','Help','Logout'])]
        for title,items in groups:
            self.label(self.sidebar,title,10,'bold',self.colors['muted']).pack(anchor='w',padx=18,pady=(8,5))
            for item in items:
                txt=self.tr(item); active=self.page==item
                b=ctk.CTkButton(self.sidebar,text=f"{self.icon(item)}  {txt}",anchor='w',height=36,corner_radius=9,fg_color=self.colors['green_light'] if active else 'transparent',text_color=self.colors['green'] if active else self.colors['text'],hover_color=self.colors['green_light'],command=lambda p=item:self.show_page(p))
                b.pack(fill='x',padx=10,pady=2)
        self.sidebar.grid_rowconfigure(99,weight=1)
        support=self.card(self.sidebar); support.pack(side='bottom',fill='x',padx=10,pady=12)
        self.label(support,'Need Help?',13,'bold').pack(anchor='w',padx=10,pady=(10,2)); self.label(support,'Open Help & Support for guidance.',10,color=self.colors['muted'],wraplength=155,justify='left').pack(anchor='w',padx=10)
        self.button(support,'Get Support',lambda:self.show_page('Help'),True).pack(fill='x',padx=10,pady=10)
    def icon(self,p): return {'Dashboard':'▦','Inventory':'▣','Purchases':'🛍','Household':'♙','Reports':'▤','Shopping':'☑','Stores':'⇄','Expiry':'◷','Expenses':'₹','Assistant':'✦','Notifications':'♢','Settings':'⚙','Help':'?','Logout':'↪'}.get(p,'•')
    def build_header(self):
        for w in self.main.winfo_children():
            if getattr(w,'_header',False): w.destroy()
        h=ctk.CTkFrame(self.main,fg_color='transparent'); h._header=True; h.grid(row=0,column=0,sticky='ew',padx=22,pady=(18,12)); h.grid_columnconfigure(1,weight=1)
        title=self.label(h,self.page+' Management',20,'bold'); title.grid(row=0,column=0,sticky='w')
        sub=self.label(h,'Monitor stock levels and manage household inventory.',10,color=self.colors['muted']); sub.grid(row=1,column=0,sticky='w')
        search=ctk.CTkEntry(h,placeholder_text='⌕  Search products...',width=300,height=36,corner_radius=18); search.grid(row=0,column=1,rowspan=2,sticky='e',padx=15); self.global_search=search
        search.bind('<Return>',lambda e:self.search_global(search.get()))
        self.button(h,'♧',lambda:self.show_page('Notifications')).grid(row=0,column=2,rowspan=2,padx=5)
        self.label(h,'👤  Admin User',12,'bold').grid(row=0,column=3,rowspan=2,padx=(10,5))
    def clear_content(self):
        for w in self.main.winfo_children():
            if not getattr(w,'_header',False): w.destroy()
    def show_page(self,page):
        if page=='Logout':
            if messagebox.askyesno('Exit','Close Smart Grocery & Household Manager?'): self.destroy()
            return
        self.page=page; self.build_sidebar(); self.build_header(); self.clear_content()
        self.content=ctk.CTkScrollableFrame(self.main,fg_color='transparent'); self.content.grid(row=1,column=0,sticky='nsew',padx=18,pady=(0,16)); self.content.grid_columnconfigure(0,weight=1)
        render={'Inventory':self.page_inventory,'Dashboard':self.page_dashboard,'Purchases':self.page_purchases,'Household':self.page_household,'Reports':self.page_reports,'Shopping':self.page_shopping,'Stores':self.page_stores,'Expiry':self.page_expiry,'Expenses':self.page_expenses,'Assistant':self.page_assistant,'Notifications':self.page_notifications,'Settings':self.page_settings,'Help':self.page_help}.get(page,self.page_inventory)
        try:
            render()
        except Exception as exc:
            logging.exception('Failed to render page %s', page)
            self.label(self.content,'This page could not be loaded. Your data has not been intentionally changed. Check logs/application.log for details.',12,color=self.colors['red'],wraplength=900,justify='left').pack(anchor='w',padx=12,pady=12)
            messagebox.showerror('Page could not be loaded', f'{page}: {exc}\n\nIf the project folder is writable, see logs/application.log for details.')
    def section(self,parent,title,actions=None):
        row=ctk.CTkFrame(parent,fg_color='transparent'); row.pack(fill='x',pady=(5,10)); self.label(row,title,17,'bold').pack(side='left')
        if actions:
            for txt,cmd in actions: self.button(row,txt,cmd,True).pack(side='right',padx=4)
    def stats(self,parent,items):
        wrap=ctk.CTkFrame(parent,fg_color='transparent'); wrap.pack(fill='x',pady=(0,14));
        for i,(title,value,sub) in enumerate(items):
            wrap.grid_columnconfigure(i,weight=1); box=self.card(wrap); box.grid(row=0,column=i,sticky='ew',padx=(0 if i==0 else 6,6 if i<len(items)-1 else 0),ipadx=5,ipady=8)
            self.label(box,title,11,color=self.colors['muted']).pack(anchor='w',padx=14,pady=(10,1)); self.label(box,value,23,'bold').pack(anchor='w',padx=14); self.label(box,sub,10,color=self.colors['green']).pack(anchor='w',padx=14,pady=(0,9))
    def table(self,parent,columns,rows,height=12):
        # Every cell is a real bordered widget: vertical and horizontal grid
        # lines are part of the table, not pipe characters appended to values.
        # All headings and data cells are centered for spreadsheet alignment.
        return SpreadsheetGridTable(parent, columns, rows, self, height)
    def search_global(self,q):
        if not q.strip(): return
        rows=self.db.rows('SELECT id,name,quantity,unit FROM products WHERE name LIKE ? ORDER BY name LIMIT 30',(f'%{q}%',))
        if rows:
            self.show_page('Inventory'); self.inventory_search.delete(0,'end'); self.inventory_search.insert(0,q); self.refresh_inventory()
        else: messagebox.showinfo('Search',f'No products matched “{q}”.')
    def focus_search(self): self.global_search.focus_set()
    def open_add_for_page(self):
        {'Inventory':self.add_product_dialog,'Household':self.add_member_dialog,'Expenses':self.add_expense_dialog,'Shopping':self.add_shopping_dialog,'Purchases':self.add_purchase_dialog,'Stores':self.add_price_dialog,'Expiry':self.add_waste_dialog}.get(self.page,self.add_product_dialog)()

    # Inventory
    def page_inventory(self):
        products=self.db.rows('SELECT p.*,c.name category,s.name store FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN stores s ON s.id=p.store_id ORDER BY p.name')
        low=sum(1 for p in products if 0<p['quantity']<=p['min_quantity']); out=sum(1 for p in products if p['quantity']<=0)
        cats={}
        for p in products: cats[p['category'] or 'Other']=cats.get(p['category'] or 'Other',0)+1
        top=max(cats,key=cats.get) if cats else '—'
        self.stats(self.content,[('Total Products',str(len(products)),'Items tracked'),('Low Stock',str(low),'Needs attention'),('Out Of Stock',str(out),'Restock required'),('Top Category',top,f'{cats.get(top,0)} products')])
        panel=self.card(self.content); panel.pack(fill='both',expand=True,pady=2)
        head=ctk.CTkFrame(panel,fg_color='transparent'); head.pack(fill='x',padx=16,pady=(14,7)); self.label(head,'Product Inventory',17,'bold').pack(side='left')
        self.button(head,'⇩ Export',self.export_inventory,True).pack(side='right')
        controls=ctk.CTkFrame(panel,fg_color='transparent'); controls.pack(fill='x',padx=15,pady=7)
        self.inventory_filter=tk.StringVar(value='All Products'); self.filter_menu=ctk.CTkSegmentedButton(controls,values=['All Products','In Stock','Low Stock','Out Of Stock'],variable=self.inventory_filter,command=lambda _:self.refresh_inventory()); self.filter_menu.pack(side='left')
        self.inventory_search=ctk.CTkEntry(controls,placeholder_text='⌕  Search inventory...',width=210); self.inventory_search.pack(side='right',padx=4); self.inventory_search.bind('<KeyRelease>',lambda e:self.refresh_inventory())
        self.button(controls,'＋ Add Product',self.add_product_dialog,True).pack(side='right',padx=5)
        self.inventory_table_frame=ctk.CTkFrame(panel,fg_color='transparent'); self.inventory_table_frame.pack(fill='both',expand=True,padx=12,pady=5)
        self.refresh_inventory()
    def refresh_inventory(self):
        if not hasattr(self,'inventory_table_frame') or not self.inventory_table_frame.winfo_exists(): return
        for w in self.inventory_table_frame.winfo_children(): w.destroy()
        q=self.inventory_search.get().strip() if hasattr(self,'inventory_search') else ''; rows=self.db.rows('SELECT p.id,p.name,c.name category,p.quantity,p.unit,p.min_quantity,p.price,s.name store FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN stores s ON s.id=p.store_id WHERE p.name LIKE ? ORDER BY p.name',(f'%{q}%',))
        f=self.inventory_filter.get() if hasattr(self,'inventory_filter') else 'All Products'
        if f=='In Stock': rows=[r for r in rows if r['quantity']>r['min_quantity']]
        elif f=='Low Stock': rows=[r for r in rows if 0<r['quantity']<=r['min_quantity']]
        elif f=='Out Of Stock': rows=[r for r in rows if r['quantity']<=0]
        cols=['Product Name','Category','Stock Level','Minimum','Amount','Store','Status','Action']; display=[]
        for r in rows:
            status='Out of Stock' if r['quantity']<=0 else ('Low Stock' if r['quantity']<=r['min_quantity'] else 'In Stock')
            display.append({'Product Name':r['name'],'Category':r['category'] or 'Other','Stock Level':f"{r['quantity']:g} {r['unit']}",'Minimum':f"{r['min_quantity']:g}",'Amount':self.fmt(r['price']),'Store':r['store'] or '—','Status':status,'Action':'•••','_id':r['id']})
        tree=self.table(self.inventory_table_frame,cols,display,13); self.inventory_tree=tree
        if not display:
            message='No products yet. Select Add Product to start your inventory.' if not q else f'No products matched “{q}”. Clear the search or add a product.'
            self.label(self.inventory_table_frame,message,11,color=self.colors['muted']).pack(anchor='w',padx=10,pady=8)
        tree.bind('<Double-1>',lambda e:self.edit_selected_product())
        tree.bind('<Button-3>',self.inventory_context)
        foot=self.label(self.inventory_table_frame,f'Showing {len(display)} products  •  Double-click a row to edit',10,color=self.colors['muted']); foot.pack(anchor='w',padx=8,pady=5)
    def inventory_context(self,event):
        item=self.inventory_tree.identify_row(event.y)
        if item: self.inventory_tree.selection_set(item); menu=tk.Menu(self,tearoff=0); menu.add_command(label='Edit product',command=self.edit_selected_product); menu.add_command(label='Delete product',command=self.delete_selected_product); menu.post(event.x_root,event.y_root)
    def selected_id(self,tree):
        sel=tree.selection()
        if not sel: return None
        tag=tree.item(sel[0],'tags'); return int(tag[0]) if tag and tag[0] else None
    def add_product_dialog(self,pid=None):
        old=self.db.one('SELECT p.*,c.name category,s.name store FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN stores s ON s.id=p.store_id WHERE p.id=?',(pid,)) if pid else {}
        fields=[('name','Product Name',old.get('name','')),('category','Category',old.get('category','Grocery')),('brand','Brand',old.get('brand','')),('unit','Unit (kg/L/pcs)',old.get('unit','pcs')),('quantity','Current Quantity',str(old.get('quantity',0))),('min_quantity','Minimum Stock',str(old.get('min_quantity',1))),('price','Unit Price',str(old.get('price','0.00'))),('store','Preferred Store',old.get('store',''))]
        if not pid: fields.append(('expiry_date','Opening Batch Expiry Date (YYYY-MM-DD)',''))
        vals=self.form_dialog('Edit Product' if pid else 'Add Product',fields,allow_zero_quantity=True)
        if vals is None:return
        try:
            if pid:self.db.update_product(pid,vals)
            else:self.db.add_product(vals)
            self.db.generate_notifications(); self.show_page(self.page)
        except Exception as e: messagebox.showerror('Product error',str(e))
    def edit_selected_product(self):
        pid=self.selected_id(self.inventory_tree)
        if pid:self.add_product_dialog(pid)
    def delete_selected_product(self):
        pid=self.selected_id(self.inventory_tree)
        if pid and messagebox.askyesno('Delete product','Delete this product?'):
            try:self.db.delete_product(pid); self.show_page('Inventory')
            except Exception as e:messagebox.showerror('Cannot delete',str(e))
    def export_inventory(self):
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv'),('Excel','*.xlsx')])
        if not path:return
        rows=self.db.rows('SELECT p.name,c.name category,p.quantity,p.unit,p.min_quantity,p.price,s.name store FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN stores s ON s.id=p.store_id')
        try:
            if Path(path).suffix.lower()=='.xlsx':
                from openpyxl import Workbook
                wb=Workbook(); ws=wb.active; ws.append(list(rows[0].keys()) if rows else ['No data'])
                for r in rows:ws.append([spreadsheet_safe(v) for v in r.values()])
                wb.save(path)
            else:
                with open(path,'w',newline='',encoding='utf-8-sig') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0].keys()) if rows else ['name']); w.writeheader(); w.writerows([{k:spreadsheet_safe(v) for k,v in r.items()} for r in rows])
            messagebox.showinfo('Export',f'Exported {len(rows)} products.')
        except Exception as e:messagebox.showerror('Export failed',str(e))

    # General dialogs and module pages
    def validate_form_values(self, values, allow_zero_quantity=False, optional_ids=None):
        """Validate common form fields before any dialog can submit."""
        from datetime import date
        date_fields={'date':'Date','list_date':'List date','purchase_date':'Purchase date','recorded_date':'Recorded date','next_due':'Next due date','start_date':'Start date','end_date':'End date','expiry_date':'Expiry date'}
        optional_dates={'expiry_date'}
        for key,label in date_fields.items():
            if key not in values: continue
            value=values.get(key,'')
            if key in optional_dates and not value: continue
            try:
                parsed=date.fromisoformat(value)
            except (TypeError,ValueError):
                raise ValueError(f'{label} must be a real date in YYYY-MM-DD format.')
            if parsed.isoformat()!=value:
                raise ValueError(f'{label} must use YYYY-MM-DD format.')
            if key in {'date','purchase_date','recorded_date'} and parsed > date.today():
                raise ValueError(f'{label} cannot be in the future.')
        if values.get('start_date') and values.get('end_date'):
            if values['end_date'] < values['start_date']:
                raise ValueError('End date cannot be earlier than start date.')
        if values.get('expiry_date'):
            if values['expiry_date'] <= date.today().isoformat():
                raise ValueError('Expiry date must be a future date (after today).')
            reference_date = values.get('purchase_date')
            if reference_date and values['expiry_date'] < reference_date:
                raise ValueError('Expiry date cannot be earlier than the purchase date.')
            if not reference_date and values.get('quantity') is not None and Decimal(values['quantity'])<=0:
                raise ValueError('An opening expiry date requires a positive opening stock quantity.')
        positive={'quantity':'Quantity','package_quantity':'Package quantity','interval_days':'Repeat interval'}
        if allow_zero_quantity and 'quantity' in values: positive.pop('quantity',None)
        nonnegative={'min_quantity':'Minimum stock','price':'Price','unit_price':'Unit price','unit_cost':'Unit cost','amount':'Amount'}
        for key,label in positive.items():
            if key in values:
                try: number=Decimal(values[key])
                except Exception: raise ValueError(f'{label} must be a valid number.')
                if not number.is_finite() or number<=0 or not math.isfinite(float(number)) or float(number)<1.0e-9 or float(number)>1.0e308: raise ValueError(f'{label} must be a finite, safely representable number greater than zero.')
        if allow_zero_quantity and 'quantity' in values:
            try: q=Decimal(values['quantity'])
            except Exception: raise ValueError('Current quantity must be a valid number.')
            if not q.is_finite() or q<0 or not math.isfinite(float(q)) or float(q)>1.0e308 or (0<float(q)<1.0e-9): raise ValueError('Current quantity must be zero or a finite value of at least 1e-9.')
        for key,label in nonnegative.items():
            if key in values:
                try: number=Decimal(values[key])
                except Exception: raise ValueError(f'{label} must be a valid number.')
                if not number.is_finite() or number<0 or not math.isfinite(float(number)) or float(number)>1.0e308 or (key in {'quantity','min_quantity'} and 0<float(number)<1.0e-9): raise ValueError(f'{label} must be zero or a finite, safely representable value of at least 1e-9.')
                if key=='amount' and (number<=0 or money(number)<=0): raise ValueError('Amount must be at least 0.01 after currency rounding.')
        for key,label in [('interval_days','Repeat interval')]:
            if key in values:
                try:
                    if Decimal(values[key]) != Decimal(values[key]).to_integral_value(): raise ValueError
                except Exception: raise ValueError(f'{label} must be a whole number of days.')
        optional_ids=set(optional_ids or {'member_id'})
        for key,label in [('product_id','Product ID'),('store_id','Store ID'),('member_id','Member ID'),('list_id','List ID'),('purchase_item_id','Purchase item ID')]:
            if key not in values: continue
            value=values.get(key,'')
            if not value and key in optional_ids: continue
            if not value: raise ValueError(f'{label} is required.')
            try: n=int(value)
            except Exception: raise ValueError(f'{label} must be a valid whole number.')
            if n<=0: raise ValueError(f'{label} must be greater than zero.')
        for key,label in [('name','Name'),('category','Category'),('reason','Reason'),('unit','Unit'),('package_unit','Package unit'),('payment_method','Payment method'),('priority','Priority')]:
            if key in values and not values[key].strip(): raise ValueError(f'{label} is required.')
        if 'name' in values and ('quantity' in values or 'min_quantity' in values or 'price' in values):
            from database import _product_name
            _product_name(values['name'])

    def form_dialog(self,title,fields,allow_zero_quantity=False):
        win=ctk.CTkToplevel(self); win.title(title); win.geometry('470x620'); win.transient(self); win.grab_set(); win.configure(fg_color=self.colors['main'])
        self.label(win,title,20,'bold').pack(anchor='w',padx=22,pady=(18,10)); body=ctk.CTkScrollableFrame(win,fg_color='transparent'); body.pack(fill='both',expand=True,padx=15)
        entries={}
        for key,label,value in fields:
            self.label(body,label,11,'bold',self.colors['muted']).pack(anchor='w',padx=8,pady=(8,2)); e=ctk.CTkEntry(body,height=35); e.pack(fill='x',padx=8); e.insert(0,str(value)); entries[key]=e
        result={}
        def save():
            values={k:e.get().strip() for k,e in entries.items()}
            try:
                self.validate_form_values(values, allow_zero_quantity=allow_zero_quantity)
            except Exception as exc:
                logging.exception('Form validation failed for %s', title)
                messagebox.showerror('Invalid input',str(exc),parent=win)
                return
            result.update(values); win.destroy()
        self.button(win,'Save',save,True).pack(fill='x',padx=22,pady=16)
        self.wait_window(win); return result or None
    def member_dialog(self, member_id=None):
        """Country-aware member editor. Phone numbers are stored in E.164 format."""
        from phone_utils import country_options, normalize_phone, national_from_e164
        existing = self.db.one('SELECT * FROM household_members WHERE id=?', (member_id,)) if member_id else {}
        countries = country_options()
        by_label = {label: (region, code) for label, region, code in countries}
        default_region = 'IN'
        current_region = default_region
        current_national = ''
        old_phone = (existing or {}).get('phone', '')
        if old_phone:
            import phonenumbers
            try:
                parsed = phonenumbers.parse(old_phone, None)
                detected = phonenumbers.region_code_for_number(parsed)
                if detected in {item[1] for item in countries}:
                    current_region = detected
                    current_national = str(parsed.national_number)
            except phonenumbers.NumberParseException:
                current_national = old_phone
        selected_label = next((label for label, region, _ in countries if region == current_region), countries[0][0])
        win = ctk.CTkToplevel(self)
        win.title('Edit Household Member' if member_id else 'Add Household Member')
        win.geometry('500x520'); win.transient(self); win.grab_set(); win.configure(fg_color=self.colors['main'])
        self.label(win, 'Edit Household Member' if member_id else 'Add Household Member', 20, 'bold').pack(anchor='w', padx=22, pady=(18, 12))
        body = ctk.CTkFrame(win, fg_color='transparent'); body.pack(fill='both', expand=True, padx=22)
        self.label(body, 'Name', 11, 'bold', self.colors['muted']).pack(anchor='w', pady=(6, 2))
        name_entry = ctk.CTkEntry(body, height=36); name_entry.pack(fill='x')
        name_entry.insert(0, (existing or {}).get('name', ''))
        self.label(body, 'Role (Owner / Adult / Member)', 11, 'bold', self.colors['muted']).pack(anchor='w', pady=(12, 2))
        role_menu = ctk.CTkOptionMenu(body, values=['Owner', 'Adult', 'Member'], height=36)
        role_menu.pack(fill='x'); role_menu.set((existing or {}).get('role', 'Member'))
        self.label(body, 'Country / Region', 11, 'bold', self.colors['muted']).pack(anchor='w', pady=(12, 2))
        country_menu = ctk.CTkOptionMenu(body, values=[item[0] for item in countries], height=36)
        country_menu.pack(fill='x'); country_menu.set(selected_label)
        calling_label = self.label(body, 'Calling code: +91', 10, color=self.colors['muted']); calling_label.pack(anchor='w', pady=(7, 1))
        self.label(body, 'Phone number (national number only)', 11, 'bold', self.colors['muted']).pack(anchor='w', pady=(7, 2))
        phone_entry = ctk.CTkEntry(body, height=36, placeholder_text='Enter number without country code')
        phone_entry.pack(fill='x'); phone_entry.insert(0, current_national)
        def update_calling_code(_value=None):
            region, code = by_label[country_menu.get()]
            calling_label.configure(text=f'Calling code: +{code}')
        country_menu.configure(command=update_calling_code)
        result = {}
        def save():
            name = name_entry.get().strip()
            role = role_menu.get().strip()
            if not name or len(name) > 100:
                messagebox.showerror('Invalid input', 'Enter a member name between 1 and 100 characters.', parent=win); return
            if role not in {'Owner', 'Adult', 'Member'}:
                messagebox.showerror('Invalid input', 'Select a valid household role.', parent=win); return
            region, _code = by_label[country_menu.get()]
            try:
                phone = normalize_phone(phone_entry.get(), region)
                values = {'name': name, 'role': role, 'phone': phone}
                if member_id:
                    self.db.update_member(member_id, values)
                else:
                    self.db.add_member(values)
            except Exception as exc:
                messagebox.showerror('Invalid member details', str(exc), parent=win); return
            result['saved'] = True
            win.destroy()
        self.button(win, 'Save Member', save, True).pack(fill='x', padx=22, pady=18)
        self.wait_window(win)
        if result.get('saved'):
            self.show_page('Household')

    def add_member_dialog(self):
        self.member_dialog()

    def page_household(self):
        self.section(self.content, 'Household Members', [('＋ Add Member', self.add_member_dialog)])
        rows = self.db.rows('SELECT id,name,role,phone,created_at FROM household_members ORDER BY name')
        display_rows = []
        for row in rows:
            item = dict(row)
            item['_id'] = item['id']
            item.pop('id', None)
            display_rows.append(item)
        tree = self.table(self.content, ['name','role','phone','created_at'], display_rows, 15)
        if not rows:
            self.label(self.content, 'No household members have been added yet.', 11, color=self.colors['muted']).pack(anchor='w', padx=8)
        member_actions = ctk.CTkFrame(self.content, fg_color='transparent'); member_actions.pack(pady=8)
        self.button(member_actions, 'Edit selected member', lambda: self.edit_member_selected(tree)).pack(side='left', padx=6)
        self.button(member_actions, 'Delete selected member', lambda: self.delete_member_selected(tree)).pack(side='left', padx=6)

    def edit_member_selected(self, tree):
        mid = self.selected_id(tree)
        if mid:
            self.member_dialog(mid)

    def delete_member_selected(self, tree):
        mid = self.selected_id(tree)
        if mid and messagebox.askyesno('Delete member', 'Delete this household member? Existing transactions will retain their records without a member link.'):
            try:
                self.db.execute('DELETE FROM household_members WHERE id=?', (mid,))
                self.show_page('Household')
            except Exception as exc:
                logging.exception('Could not delete household member')
                messagebox.showerror('Member error', str(exc))

    def page_purchases(self):
        self.section(self.content,'Purchase History',[('＋ Record Purchase',self.add_purchase_dialog)])
        rows=self.db.rows('SELECT p.id,p.purchase_date,COALESCE(s.name,"—") store,p.payment_method,p.total FROM purchases p LEFT JOIN stores s ON s.id=p.store_id ORDER BY p.id DESC')
        for r in rows:
            r['_id']=r['id']; r.pop('id',None); r['total']=self.fmt(r['total'])
        tree=self.table(self.content,['purchase_date','store','payment_method','total'],rows,16)
        if not rows:self.label(self.content,'No purchases recorded yet. Use Record Purchase to add your first transaction.',11,color=self.colors['muted']).pack(anchor='w',padx=8)
        purchase_actions=ctk.CTkFrame(self.content,fg_color='transparent'); purchase_actions.pack(pady=8)
        for text,command in [('Edit selected purchase (all items)',lambda:self.edit_purchase_selected(tree)),('Return selected purchase item',lambda:self.return_purchase_selected(tree)),('Delete selected purchase',lambda:self.delete_purchase_selected(tree))]:
            self.button(purchase_actions,text,command).pack(side='left',padx=6)
    def purchase_editor(self, title, purchase=None, existing_items=None):
        """Friendly purchase form: select product/store by name, never type database IDs."""
        products=self.db.rows('SELECT id,name,price FROM products ORDER BY name')
        stores=self.db.rows('SELECT id,name FROM stores ORDER BY name')
        if not products:
            messagebox.showwarning('Purchase','Add at least one product in Inventory before recording a purchase.')
            return
        win=ctk.CTkToplevel(self); win.title(title); win.geometry('900x760'); win.minsize(760,620); win.transient(self); win.grab_set(); win.configure(fg_color=self.colors['main'])
        self.label(win,title,20,'bold').pack(anchor='w',padx=22,pady=(16,8))
        body=ctk.CTkScrollableFrame(win,fg_color='transparent'); body.pack(fill='both',expand=True,padx=16,pady=4)
        fields={}
        defaults={'purchase_date':(purchase or {}).get('purchase_date',date.today().isoformat()),'payment_method':(purchase or {}).get('payment_method','Cash'),'notes':(purchase or {}).get('notes','')}
        for key,label in [('purchase_date','Purchase date (YYYY-MM-DD)'),('payment_method','Payment method'),('notes','Notes')]:
            self.label(body,label,11,'bold',self.colors['muted']).pack(anchor='w',padx=8,pady=(7,2))
            e=ctk.CTkEntry(body,height=34); e.pack(fill='x',padx=8); e.insert(0,str(defaults[key])); fields[key]=e
        store_names=['— No store selected —']+[x['name'] for x in stores]
        selected_store='— No store selected —'
        if purchase and purchase.get('store_id'):
            selected_store=next((x['name'] for x in stores if x['id']==purchase['store_id']),selected_store)
        self.label(body,'Store (optional)',11,'bold',self.colors['muted']).pack(anchor='w',padx=8,pady=(7,2))
        store_box=ctk.CTkComboBox(body,values=store_names,height=34); store_box.pack(fill='x',padx=8); store_box.set(selected_store)
        self.label(body,'Purchase items',13,'bold').pack(anchor='w',padx=8,pady=(14,4))
        self.label(body,'Choose a product by name, then enter quantity, unit price and optional future expiry date.',10,color=self.colors['muted']).pack(anchor='w',padx=8)
        item_area=ctk.CTkFrame(body,fg_color=self.colors['card'],corner_radius=10); item_area.pack(fill='x',padx=8,pady=7)
        item_rows=[]; product_names=[x['name'] for x in products]; product_by_name={x['name']:x for x in products}
        def add_item_row(initial=None):
            initial=initial or {}; row=ctk.CTkFrame(item_area,fg_color='transparent'); row.pack(fill='x',padx=6,pady=5)
            row.grid_columnconfigure(0,weight=3); row.grid_columnconfigure(1,weight=1); row.grid_columnconfigure(2,weight=1); row.grid_columnconfigure(3,weight=2)
            self.label(row,'Product',10,'bold',self.colors['muted']).grid(row=0,column=0,sticky='w',padx=4)
            self.label(row,'Quantity',10,'bold',self.colors['muted']).grid(row=0,column=1,sticky='w',padx=4)
            self.label(row,'Unit price',10,'bold',self.colors['muted']).grid(row=0,column=2,sticky='w',padx=4)
            self.label(row,'Expiry date (optional)',10,'bold',self.colors['muted']).grid(row=0,column=3,sticky='w',padx=4)
            prod=ctk.CTkComboBox(row,values=product_names,height=32); prod.grid(row=1,column=0,sticky='ew',padx=4,pady=(2,3))
            qty=ctk.CTkEntry(row,height=32); qty.grid(row=1,column=1,sticky='ew',padx=4,pady=(2,3))
            price=ctk.CTkEntry(row,height=32); price.grid(row=1,column=2,sticky='ew',padx=4,pady=(2,3))
            expiry=ctk.CTkEntry(row,height=32,placeholder_text='YYYY-MM-DD'); expiry.grid(row=1,column=3,sticky='ew',padx=4,pady=(2,3))
            product=next((x for x in products if x['id']==initial.get('product_id')),products[0])
            prod.set(product['name']); qty.insert(0,str(initial.get('quantity',1))); price.insert(0,str(initial.get('unit_price',product['price']))); expiry.insert(0,str(initial.get('expiry_date') or ''))
            record={'frame':row,'product':prod,'quantity':qty,'price':price,'expiry':expiry}; item_rows.append(record)
            def remove():
                if len(item_rows)<=1:
                    messagebox.showinfo('Purchase items','At least one purchase item is required.',parent=win); return
                item_rows.remove(record); row.destroy()
            self.button(row,'Remove',remove).grid(row=1,column=4,padx=5)
        for it in (existing_items or []): add_item_row(dict(it))
        if not item_rows: add_item_row()
        self.button(body,'＋ Add another product',add_item_row).pack(anchor='w',padx=8,pady=6)
        total_label=self.label(body,'Estimated purchase total: '+self.fmt(0),12,'bold',self.colors['green']); total_label.pack(anchor='e',padx=12,pady=8)
        def calculate_total():
            total=Decimal('0')
            for r in item_rows:
                try:
                    q=Decimal(r['quantity'].get().strip()); price=Decimal(r['price'].get().strip())
                    if q.is_finite() and price.is_finite() and q>0 and price>=0: total+=q*price
                except Exception: pass
            total_label.configure(text='Estimated purchase total: '+self.fmt(total))
        for r in item_rows:
            for key in ('quantity','price'): r[key].bind('<KeyRelease>',lambda _e:calculate_total())
        def save():
            try:
                v={k:e.get().strip() for k,e in fields.items()}
                self.validate_form_values({'purchase_date':v['purchase_date'],'payment_method':v['payment_method']})
                selected=store_box.get().strip(); store_id=next((x['id'] for x in stores if x['name']==selected),None)
                if selected not in store_names: raise ValueError('Choose a store from the dropdown or select no store.')
                items=[]
                for index,r in enumerate(item_rows,1):
                    name=r['product'].get().strip(); product=product_by_name.get(name)
                    if not product: raise ValueError(f'Purchase item {index}: choose a valid product from the dropdown.')
                    q=r['quantity'].get().strip(); price=r['price'].get().strip(); expiry=r['expiry'].get().strip()
                    self.validate_form_values({'quantity':q,'unit_price':price})
                    if expiry: self.validate_form_values({'expiry_date':expiry,'purchase_date':v['purchase_date']})
                    items.append({'product_id':product['id'],'quantity':q,'unit_price':price,'expiry_date':expiry or None})
                if not items: raise ValueError('Add at least one purchase item.')
                payload={'purchase_date':v['purchase_date'],'store_id':store_id,'payment_method':v['payment_method'],'notes':v['notes'],'items':items}
                if purchase: self.db.update_purchase(purchase['id'],payload)
                else: self.db.create_purchase(payload)
                self.db.generate_notifications(); win.destroy(); self.show_page('Purchases')
            except Exception as e:
                logging.exception('Could not save purchase')
                messagebox.showerror('Purchase error',str(e),parent=win)
        self.button(win,'Save Purchase',save,True).pack(fill='x',padx=22,pady=14)
        self.wait_window(win)
    def edit_purchase_selected(self,tree):
        pid=self.selected_id(tree)
        if not pid:return
        p=self.db.one('SELECT * FROM purchases WHERE id=?',(pid,))
        items=self.db.rows('SELECT pi.*,b.expiry_date FROM purchase_items pi LEFT JOIN product_batches b ON b.id=pi.batch_id WHERE pi.purchase_id=? ORDER BY pi.id',(pid,))
        self.purchase_editor('Edit Purchase',dict(p),items)
    def return_purchase_selected(self,tree):
        pid=self.selected_id(tree)
        if not pid:return
        items=self.db.rows('SELECT pi.id,p.name,pi.quantity,pi.unit_price FROM purchase_items pi JOIN products p ON p.id=pi.product_id WHERE pi.purchase_id=?',(pid,))
        if not items:return
        it=items[0]
        v=self.form_dialog('Return Purchase Item',[('purchase_item_id','Item ID — '+' | '.join(f"{x['id']}:{x['name']} (qty {x['quantity']})" for x in items),str(it['id'])),('quantity','Return Quantity','1'),('reason','Reason','Returned to store')])
        if v:
            try:self.db.return_purchase_item(int(v['purchase_item_id']),v['quantity'],v['reason']);self.show_page('Purchases')
            except Exception as e:messagebox.showerror('Return failed',str(e))
    def add_purchase_dialog(self):
        self.purchase_editor('Record Purchase')
    def delete_purchase_selected(self,tree):
        pid=self.selected_id(tree)
        if pid and messagebox.askyesno('Delete purchase','Reverse this purchase and its stock/expense effects?'):
            try:self.db.delete_purchase(pid);self.show_page('Purchases')
            except Exception as e:messagebox.showerror('Cannot delete purchase',str(e))
    def page_shopping(self):
        created=self.db.generate_due_recurring_lists()
        self.section(self.content,'Shopping Lists',[('＋ New List',self.add_list_dialog),('＋ Add Item',self.add_shopping_dialog),('＋ Recurring Schedule',self.add_recurring_dialog)])
        schedules=self.db.recurring_schedules()
        if schedules:
            self.section(self.content,'Recurring Shopping Schedules')
            st=self.table(self.content,['id','name','interval_days','next_due','active','last_generated'],schedules,4)
            controls=ctk.CTkFrame(self.content,fg_color='transparent');controls.pack(fill='x',pady=(0,8))
            self.button(controls,'Pause / Resume selected',lambda:self.toggle_recurring(st)).pack(side='left')
            self.label(self.content,f'{len(created)} due shopping list(s) generated automatically.' if created else 'Schedules are checked whenever this page opens.',10,color=self.colors['muted']).pack(anchor='w')
        lists=self.db.rows("SELECT * FROM shopping_lists WHERE notes!='Recurring schedule template' AND notes NOT LIKE 'recurring-template:%' ORDER BY id DESC")
        if not lists and not schedules:
            self.label(self.content,'No shopping lists yet. Create a list or add a recurring schedule to begin.',12,color=self.colors['muted']).pack(anchor='w',padx=8,pady=12)
        for l in lists:
            box=self.card(self.content);box.pack(fill='x',pady=6); self.label(box,f"{l['name']}  •  {self.format_date(l['list_date'])}  •  {l['status']}",15,'bold').pack(anchor='w',padx=14,pady=8)
            items=self.db.rows('SELECT id,name,category,quantity,unit,unit_price,status,priority FROM shopping_list_items WHERE list_id=? ORDER BY id',(l['id'],))
            total=shopping_estimated_total(items)
            for item in items:item['unit_price']=self.fmt(item['unit_price'])
            self.label(box,f'{len(items)} items  •  Estimated total {self.fmt(total)}  •  Purchased {sum(i["status"]=="Purchased" for i in items)}',11,color=self.colors['muted']).pack(anchor='w',padx=14,pady=(0,6))
            if items:
                item_tree=self.table(box,['id','name','category','quantity','unit','unit_price','status','priority'],items,4)
                controls=ctk.CTkFrame(box,fg_color='transparent');controls.pack(fill='x',padx=10,pady=(0,9))
                self.button(controls,'Edit selected item',lambda t=item_tree:self.edit_shopping_item(t)).pack(side='left',padx=3)
                self.button(controls,'Remove selected item',lambda t=item_tree:self.remove_shopping_item(t)).pack(side='left',padx=3)
                self.button(controls,'Convert selected item to purchase',lambda t=item_tree,lid=l['id']:self.convert_shopping_item(t,lid),True).pack(side='right',padx=3)

    def add_recurring_dialog(self):
        v=self.form_dialog('Create Recurring Shopping Schedule',[('name','Schedule Name','Weekly essentials'),('interval_days','Repeat every N days','7'),('next_due','First due date (YYYY-MM-DD)',date.today().isoformat()),('items','Items separated by ; (name, quantity, unit, price)','Milk, 2, L, 30; Rice, 1, kg, 60')])
        if not v:return
        try:
            items=[]
            for raw in v['items'].split(';'):
                if not raw.strip():continue
                parts=[x.strip() for x in raw.split(',')]
                if len(parts)!=4 or not parts[0] or not parts[2] or not parts[3]:
                    raise ValueError('Each recurring item must use: name, quantity, unit, estimated unit price.')
                items.append({'name':parts[0],'quantity':parts[1],'unit':parts[2],'unit_price':parts[3]})
            if not items:raise ValueError('Add at least one recurring item.')
            self.db.create_recurring_schedule(v['name'],v['interval_days'],v['next_due'],items)
            self.show_page('Shopping')
        except Exception as e:messagebox.showerror('Recurring schedule error',str(e))

    def toggle_recurring(self,tree):
        sid=self.selected_id(tree)
        if not sid:return
        row=self.db.one('SELECT active FROM recurring_shopping WHERE id=?',(sid,))
        if row:
            self.db.set_recurring_schedule_active(sid,not bool(row['active']))
            self.show_page('Shopping')

    def edit_shopping_item(self,tree):
        iid=self.selected_id(tree)
        if not iid:return
        r=self.db.one('SELECT * FROM shopping_list_items WHERE id=?',(iid,))
        if not r:return
        v=self.form_dialog('Edit Shopping Item',[('name','Name',r['name']),('category','Category',r['category']),('quantity','Quantity',str(r['quantity'])),('unit','Unit',r['unit']),('unit_price','Estimated Unit Price',r['unit_price']),('priority','Priority',r['priority'])])
        if v:
            try:self.db.update_shopping_item(iid,v);self.show_page('Shopping')
            except Exception as e:messagebox.showerror('Shopping item error',str(e))
    def remove_shopping_item(self,tree):
        iid=self.selected_id(tree)
        if iid and messagebox.askyesno('Remove item','Remove this pending shopping item?'):
            try:self.db.delete_shopping_item(iid);self.show_page('Shopping')
            except Exception as e:messagebox.showerror('Shopping item error',str(e))
    def add_list_dialog(self):
        v=self.form_dialog('Create Shopping List',[('name','List Name','Weekly Shopping'),('list_date','Date (YYYY-MM-DD)',date.today().isoformat()),('notes','Notes','')])
        if v:
            self.db.add_shopping_list(v);self.show_page('Shopping')
    def add_shopping_dialog(self):
        lists=self.db.rows("SELECT id,name FROM shopping_lists WHERE notes!='Recurring schedule template' AND notes NOT LIKE 'recurring-template:%' ORDER BY id DESC"); products=self.db.rows('SELECT id,name,price,unit FROM products ORDER BY name')
        if not lists:
            self.add_list_dialog(); lists=self.db.rows("SELECT id,name FROM shopping_lists WHERE notes!='Recurring schedule template' AND notes NOT LIKE 'recurring-template:%' ORDER BY id DESC")
            if not lists:return
        v=self.form_dialog('Add Shopping Item',[('list_id','List ID — '+' | '.join(f"{x['id']}:{x['name']}" for x in lists),str(lists[0]['id'])),('name','Item Name',''),('category','Category','Grocery'),('quantity','Quantity','1'),('unit','Unit','pcs'),('unit_price','Estimated Unit Price','0'),('priority','Priority (Low/Normal/High)','Normal')])
        if v:
            try:self.db.add_shopping_item({'list_id':int(v['list_id']),'name':v['name'],'category':v['category'],'quantity':v['quantity'],'unit':v['unit'],'unit_price':v['unit_price'],'priority':v['priority']});self.show_page('Shopping')
            except Exception as e:messagebox.showerror('Shopping list error',str(e))
    def convert_shopping_item(self,tree,list_id):
        item_id=self.selected_id(tree)
        if not item_id:
            messagebox.showinfo('Shopping list','Select an item first.'); return
        item=self.db.one('SELECT * FROM shopping_list_items WHERE id=? AND list_id=?',(item_id,list_id))
        if not item or item['status']=='Purchased':
            messagebox.showinfo('Shopping list','This item is already purchased or no longer exists.'); return
        v=self.form_dialog('Complete Shopping Item',[('quantity','Purchased Quantity',str(item['quantity'])),('unit_price','Actual Unit Price',str(item['unit_price'])),('purchase_date','Purchase Date',date.today().isoformat()),('expiry_date','Batch Expiry (YYYY-MM-DD)',''),('payment_method','Payment Method','Cash')])
        if not v:return
        try:
            purchase_id=self.db.convert_shopping_item_to_purchase(
                item_id, v['quantity'], v['unit_price'], v['purchase_date'],
                v['expiry_date'], v['payment_method'])
            self.db.generate_notifications()
            messagebox.showinfo('Purchase completed',f'Created purchase #{purchase_id}; stock, expense and shopping status were updated together.')
            self.show_page('Shopping')
        except Exception as e:messagebox.showerror('Purchase conversion failed',str(e))

    def page_stores(self):
        self.section(self.content,'Store Price Comparison',[('＋ Record Price',self.add_price_dialog),('＋ Add Store',self.add_store_dialog)])
        raw_rows=self.db.rows('SELECT p.name product,p.unit product_unit,s.name store,ph.package_quantity,ph.package_unit,ph.price,ph.recorded_date FROM price_history ph JOIN products p ON p.id=ph.product_id JOIN stores s ON s.id=ph.store_id ORDER BY p.name,CAST(ph.price AS REAL)')
        display_rows=[dict(r,price=self.fmt(r['price'])) for r in raw_rows]
        self.table(self.content,['product','store','package_quantity','package_unit','price','recorded_date'],display_rows,15)
        if not raw_rows:self.label(self.content,'No store prices recorded yet. Add stores and enter observed package prices to compare them.',11,color=self.colors['muted']).pack(anchor='w',padx=8)
        groups={}
        for r in raw_rows:
            unit=r['package_unit'].strip().lower(); factor={'kg':1000,'g':1,'l':1000,'ml':1,'pcs':1,'piece':1,'pieces':1}.get(unit)
            product_unit=str(r['product_unit']).strip().lower()
            expected='mass' if product_unit in {'kg','g','gram','grams'} else ('volume' if product_unit in {'l','ml','litre','liter','litres','liters'} else ('count' if product_unit in {'pcs','piece','pieces'} else None))
            actual='mass' if unit in {'kg','g'} else ('volume' if unit in {'l','ml'} else ('count' if unit in {'pcs','piece','pieces'} else None))
            if factor and expected==actual and float(r['package_quantity'])>0:
                canonical='kg' if unit in ('kg','g') else ('L' if unit in ('l','ml') else 'pcs')
                key=(r['product'],canonical)
                norm=float(r['price'])/(float(r['package_quantity'])*factor)
                if math.isfinite(norm):groups.setdefault(key,[]).append((norm,r['store'],r['price'],r['package_quantity']))
        self.section(self.content,'Comparable price insights')
        for (product,unit),vals in groups.items():
            if len(vals)>1:
                vals.sort(); scale=1000 if unit in ('kg','L') else 1
                best=self.fmt(vals[0][0]*scale); worst=self.fmt(vals[-1][0]*scale)
                self.label(self.content,f"{product}: best unit price is {vals[0][1]} ({best} per {unit}); highest is {vals[-1][1]} ({worst} per {unit}).",12).pack(anchor='w',padx=10,pady=3)
    def add_store_dialog(self):
        v=self.form_dialog('Add Store',[('name','Store Name',''),('address','Address',''),('notes','Notes','')])
        if v:
            try:self.db.add_store(v);self.show_page('Stores')
            except Exception as e:messagebox.showerror('Store error',str(e))
    def add_price_dialog(self):
        products=self.db.rows('SELECT id,name,unit FROM products');stores=self.db.rows('SELECT id,name FROM stores')
        if not products or not stores:messagebox.showwarning('Price comparison','Add at least one product and one store.');return
        first_unit=str(products[0]['unit']).strip().lower()
        default_package_unit={'kg':'kg','g':'g','gram':'g','grams':'g','l':'L','litre':'L','liter':'L','litres':'L','liters':'L','ml':'ml','pcs':'pcs','piece':'piece','pieces':'pieces'}.get(first_unit,'kg')
        v=self.form_dialog('Record Store Price',[('product_id','Product ID — '+' | '.join(f"{x['id']}:{x['name']} ({x['unit']})" for x in products),str(products[0]['id'])),('store_id','Store ID — '+' | '.join(f"{x['id']}:{x['name']}" for x in stores),str(stores[0]['id'])),('package_quantity','Package Quantity','1'),('package_unit','Package Unit (kg/g/L/ml/pcs)',default_package_unit),('price','Package Price','0'),('recorded_date','Date',date.today().isoformat())])
        if v:
            try:self.db.add_price_record({'product_id':int(v['product_id']),'store_id':int(v['store_id']),'package_quantity':v['package_quantity'],'package_unit':v['package_unit'],'price':v['price'],'recorded_date':v['recorded_date']});self.show_page('Stores')
            except Exception as e:messagebox.showerror('Price error',str(e))
    def page_expiry(self):
        self.section(self.content,'Expiry & FIFO Tracker',[('＋ Record Consumption',self.consume_stock_dialog),('＋ Record Wastage',self.add_waste_dialog),('Edit Selected Batch',self.edit_batch_dialog)])
        rows=self.db.rows('SELECT b.id,p.name product,b.batch_code,b.quantity,b.expiry_date,b.unit_cost FROM product_batches b JOIN products p ON p.id=b.product_id WHERE b.quantity>0 ORDER BY CASE WHEN b.expiry_date IS NULL THEN 1 ELSE 0 END,b.expiry_date')
        today=date.today()
        for r in rows:
            r['unit_cost']=self.fmt(r['unit_cost'])
            try:r['days_left']=(date.fromisoformat(r['expiry_date'])-today).days if r['expiry_date'] else 'Not set'
            except ValueError:r['days_left']='Invalid date'
            r['status']='Expired' if isinstance(r['days_left'],int) and r['days_left']<0 else ('Urgent' if isinstance(r['days_left'],int) and r['days_left']<=3 else ('Soon' if isinstance(r['days_left'],int) and r['days_left']<=7 else 'Safe'))
        self.expiry_tree=self.table(self.content,['product','batch_code','quantity','expiry_date','days_left','status','unit_cost'],rows,15)
        if not rows:self.label(self.content,'No stock batches are currently recorded.',11,color=self.colors['muted']).pack(anchor='w')
        self.label(self.content,'FIFO: batches are listed by earliest expiry first. Expired batches should be recorded as wastage and are not recommended for consumption.',11,color=self.colors['muted'],wraplength=900).pack(anchor='w',pady=10)
    def edit_batch_dialog(self):
        batch_id=self.selected_id(self.expiry_tree)
        if not batch_id:
            messagebox.showinfo('Expiry tracker','Select a stock batch first.'); return
        batch=self.db.one('SELECT * FROM product_batches WHERE id=?',(batch_id,))
        if not batch:
            messagebox.showerror('Expiry tracker','The selected batch no longer exists.'); return
        values=self.form_dialog('Edit Stock Batch',[
            ('batch_code','Batch Code',batch['batch_code'] or ''),
            ('expiry_date','Expiry Date (YYYY-MM-DD; leave blank for none)',batch['expiry_date'] or ''),
            ('unit_cost','Unit Cost',str(batch['unit_cost'])),
        ])
        if values is None:return
        try:
            self.db.update_batch(batch_id,values)
            self.db.generate_notifications()
            self.show_page('Expiry')
        except Exception as e:messagebox.showerror('Batch update failed',str(e))

    def consume_stock_dialog(self):
        products=self.db.rows('''SELECT p.id,p.name,p.unit,COALESCE(SUM(b.quantity),0) quantity FROM products p
            JOIN product_batches b ON b.product_id=p.id AND b.quantity>0 AND (b.expiry_date IS NULL OR b.expiry_date>=?)
            GROUP BY p.id HAVING COALESCE(SUM(b.quantity),0)>0 ORDER BY p.name''',(date.today().isoformat(),))
        if not products:
            messagebox.showinfo('Record Consumption','No non-expired stock is available. Expired stock should be recorded as wastage.');return
        choices=' | '.join(f"{p['id']}:{p['name']} ({p['quantity']} {p['unit']} available)" for p in products)
        values=self.form_dialog('Record Household Consumption',[
            ('product_id','Product ID — '+choices,str(products[0]['id'])),
            ('quantity','Consumed Quantity', '1'),
            ('note','Note','Household consumption')
        ])
        if values is None:return
        try:
            self.db.consume_stock(int(values['product_id']),values['quantity'],values.get('note') or 'Household consumption')
            self.db.generate_notifications()
            self.show_page('Expiry')
        except Exception as e:messagebox.showerror('Consumption error',str(e))

    def add_waste_dialog(self):
        products=self.db.rows('SELECT id,name,price FROM products WHERE quantity>0')
        if not products:messagebox.showinfo('Wastage','No products currently have stock.');return
        v=self.form_dialog('Record Food Waste',[('product_id','Product ID — '+' | '.join(f"{x['id']}:{x['name']}" for x in products),str(products[0]['id'])),('quantity','Quantity','1'),('reason','Reason','Expired'),('date','Date',date.today().isoformat()),('unit_cost','Unit Cost',products[0]['price']),('notes','Notes','')])
        if v:
            try:self.db.record_waste({'product_id':int(v['product_id']),'quantity':v['quantity'],'reason':v['reason'],'date':v['date'],'unit_cost':v['unit_cost'],'notes':v['notes']});self.show_page('Expiry')
            except Exception as e:messagebox.showerror('Wastage error',str(e))
    def page_expenses(self):
        now=date.today(); start=now.replace(day=1).isoformat(); end=now.isoformat()
        rows=self.db.rows('SELECT e.id,e.expense_date,e.category,e.description,e.amount,COALESCE(h.name,"—") member FROM expenses e LEFT JOIN household_members h ON h.id=e.member_id ORDER BY e.expense_date DESC')
        total=sum((money(r['amount']) for r in rows if r['expense_date']>=start and r['expense_date']<=end),Decimal('0'))
        active_budgets=self.db.rows('SELECT * FROM budgets WHERE start_date<=? AND end_date>=? ORDER BY category,name',(end,end))
        overall_rows=[b for b in active_budgets if b['category']=='All']
        overall_budget=sum((money(b['amount']) for b in overall_rows),Decimal('0'))
        overall_spent=Decimal('0.00')
        for budget_row in overall_rows:
            spent_row=self.db.one('SELECT COALESCE(SUM(CAST(amount AS REAL)),0) amount FROM expenses WHERE expense_date BETWEEN ? AND ?',(budget_row['start_date'],budget_row['end_date']))
            overall_spent += money(spent_row['amount'])
        if overall_budget:
            remaining=max(Decimal('0'),overall_budget-overall_spent)
            used=f'{(float(overall_spent/overall_budget)*100):.1f}%'
            budget_display=self.fmt(overall_budget)
            remaining_display=self.fmt(remaining)
        else:
            budget_display='No overall budget'
            remaining_display='—'
            used='—'
        self.stats(self.content,[('This Month Spent',self.fmt(total),'Recorded expenses'),('Overall Budget',budget_display,'Active All-category budgets'),('Remaining',remaining_display,'Overall budget only'),('Budget Used',used,'Overall budget only')])
        self.section(self.content,'Household Expenses',[('＋ Record Expense',self.add_expense_dialog),('＋ Set Budget',self.add_budget_dialog)])
        if active_budgets:
            self.section(self.content,'Active Budget Tracking')
            budget_rows=[]
            for b in active_budgets:
                spent_sql='SELECT COALESCE(SUM(CAST(amount AS REAL)),0) amount FROM expenses WHERE expense_date BETWEEN ? AND ?'
                spent_params=[b['start_date'],b['end_date']]
                if b['category']!='All':spent_sql+=' AND category=?';spent_params.append(b['category'])
                spent_amount=money(self.db.one(spent_sql,spent_params)['amount'])
                limit_amount=money(b['amount'])
                budget_rows.append({'id':b['id'],'budget':b['name'],'category':b['category'],'period':f"{self.format_date(b['start_date'])} to {self.format_date(b['end_date'])}",'spent':self.fmt(spent_amount),'limit':self.fmt(limit_amount),'used':f'{float(spent_amount/limit_amount)*100:.1f}%' if limit_amount>0 else '—'})
            budget_tree=self.table(self.content,['budget','category','period','spent','limit','used'],budget_rows,7)
            budget_actions=ctk.CTkFrame(self.content,fg_color='transparent');budget_actions.pack(fill='x',pady=(2,8))
            self.button(budget_actions,'Edit Selected Budget',lambda:self.edit_budget_selected(budget_tree)).pack(side='right',padx=4)
            self.button(budget_actions,'Configure Selected Budget Alerts',lambda:self.configure_budget_alerts(budget_tree)).pack(side='right',padx=4)
        else:
            self.label(self.content,'No active budgets cover today. Create a budget to track spending against a limit.',11,color=self.colors['muted']).pack(anchor='w',padx=8)
        for r in rows:r['amount']=self.fmt(r['amount'])
        tree=self.table(self.content,['expense_date','category','description','amount','member'],rows,13)
        controls=ctk.CTkFrame(self.content,fg_color='transparent');controls.pack(fill='x',pady=7)
        self.button(controls,'Edit selected manual expense',lambda:self.edit_expense_selected(tree)).pack(side='right',padx=4)
        self.button(controls,'Delete selected manual expense',lambda:self.delete_expense_selected(tree)).pack(side='right',padx=4)
        if overall_budget:
            pct=float(overall_spent/overall_budget)*100
            level='Budget exceeded' if pct>=100 else ('Critical warning' if pct>=90 else ('Warning' if pct>=75 else 'On track'))
            self.label(self.content,f'Budget status: {level} ({pct:.1f}% used for the budget date range).',12,color=self.colors['orange'] if pct>=75 else self.colors['green']).pack(anchor='w',pady=8)
    def edit_expense_selected(self,tree):
        eid=self.selected_id(tree)
        if not eid:return
        expense=self.db.one('SELECT * FROM expenses WHERE id=?',(eid,))
        if not expense:return
        if expense['purchase_id'] is not None:
            messagebox.showwarning('Linked expense','This expense belongs to a purchase. Edit the purchase instead so stock and expense values remain synchronized.');return
        members=self.db.rows('SELECT id,name FROM household_members ORDER BY name')
        v=self.form_dialog('Edit Expense',[('date','Date',expense['expense_date']),('category','Category',expense['category']),('description','Description',expense['description']),('amount','Amount',expense['amount']),('member_id','Member ID — '+' | '.join(f"{m['id']}:{m['name']}" for m in members),str(expense['member_id'] or ''))])
        if v:
            try:
                self.db.update_expense(eid,{'date':v['date'],'category':v['category'],'description':v['description'],'amount':v['amount'],'member_id':int(v['member_id']) if v['member_id'] else None})
                self.show_page('Expenses')
            except Exception as e:messagebox.showerror('Expense error',str(e))

    def delete_expense_selected(self,tree):
        eid=self.selected_id(tree)
        if not eid:return
        row=self.db.one('SELECT purchase_id FROM expenses WHERE id=?',(eid,))
        if row and row['purchase_id'] is not None:
            messagebox.showwarning('Linked expense','This expense belongs to a purchase. Delete the purchase to reverse both records safely.');return
        if messagebox.askyesno('Delete expense','Delete this expense record?'):
            self.db.execute('DELETE FROM expenses WHERE id=?',(eid,));self.show_page('Expenses')
    def add_expense_dialog(self):
        members=self.db.rows('SELECT id,name FROM household_members')
        v=self.form_dialog('Record Expense',[('date','Date',date.today().isoformat()),('category','Category','Groceries'),('description','Description',''),('amount','Amount','1.00'),('member_id','Member ID — '+' | '.join(f"{m['id']}:{m['name']}" for m in members),'')])
        if v:
            try:self.db.add_expense({'date':v['date'],'category':v['category'],'description':v['description'],'amount':v['amount'],'member_id':int(v['member_id']) if v['member_id'] else None});self.show_page('Expenses')
            except Exception as e:messagebox.showerror('Expense error',str(e))
    def configure_budget_alerts(self,tree):
        budget_id=self.selected_id(tree)
        if not budget_id:
            messagebox.showinfo('Budget alerts','Select an active budget first.'); return
        budget=self.db.one('SELECT * FROM budgets WHERE id=?',(budget_id,))
        if not budget:
            messagebox.showerror('Budget alerts','The selected budget no longer exists.'); return
        current=','.join(str(x) for x in (50,75,90,100) if budget[f'alert_{x}'])
        values=self.form_dialog('Configure Budget Alerts',[
            ('thresholds','Alert thresholds (50, 75, 90, 100; blank disables all)',current)
        ])
        if values is None:return
        try:
            raw=values['thresholds'].strip()
            thresholds=[] if not raw else [int(part.strip()) for part in raw.split(',') if part.strip()]
            if raw and not thresholds:raise ValueError('Enter supported thresholds or leave the field blank to disable alerts.')
            self.db.set_budget_alert_thresholds(budget_id,thresholds)
            self.db.generate_notifications()
            self.show_page('Expenses')
        except Exception as e:messagebox.showerror('Budget alert error',str(e))

    def add_budget_dialog(self):
        today=date.today(); end=today.replace(day=calendar.monthrange(today.year,today.month)[1])
        v=self.form_dialog('Set Budget',[('name','Budget Name','Monthly Household Budget'),('category','Category (All or exact category)','All'),('period','Period (Weekly/Monthly/Quarterly/Yearly/Custom)','Monthly'),('amount','Budget Amount','10000'),('start_date','Start Date',today.replace(day=1).isoformat()),('end_date','End Date',end.isoformat())])
        if v:
            try:
                self.db.add_budget(v);self.show_page('Expenses')
            except Exception as e:messagebox.showerror('Budget error',str(e))
    def edit_budget_selected(self,tree):
        budget_id=self.selected_id(tree)
        if not budget_id:
            messagebox.showinfo('Budget','Select an active budget first.');return
        budget=self.db.one('SELECT * FROM budgets WHERE id=?',(budget_id,))
        if not budget:
            messagebox.showerror('Budget','The selected budget no longer exists.');return
        values=self.form_dialog('Edit Budget',[
            ('name','Budget Name',budget['name']),('category','Category (All or exact category)',budget['category']),
            ('period','Period (Weekly/Monthly/Quarterly/Yearly/Custom)',budget['period']),('amount','Budget Amount',budget['amount']),
            ('start_date','Start Date',budget['start_date']),('end_date','End Date',budget['end_date'])
        ])
        if values is None:return
        try:
            self.db.update_budget(budget_id,values)
            self.db.generate_notifications()
            self.show_page('Expenses')
        except Exception as e:messagebox.showerror('Budget update failed',str(e))
    def page_dashboard(self):
        p=self.db.rows('SELECT quantity,min_quantity FROM products'); total=len(p); low=sum(0<x['quantity']<=x['min_quantity'] for x in p); out=sum(x['quantity']<=0 for x in p)
        today=date.today(); spent=self.db.one("SELECT COALESCE(SUM(CAST(amount AS REAL)),0) n FROM expenses WHERE strftime('%Y-%m',expense_date)=?",(today.strftime('%Y-%m'),))['n']
        self.stats(self.content,[('Total Products',total,'Across all categories'),('Low Stock',low,'Restocking needed'),('Out Of Stock',out,'Unavailable items'),('Monthly Spending',self.fmt(spent),'Current calendar month')])
        self.section(self.content,'Household Overview')
        grid=ctk.CTkFrame(self.content,fg_color='transparent');grid.pack(fill='x')
        for i,(title,sql) in enumerate([('Recent Purchases','SELECT purchase_date date,total amount FROM purchases ORDER BY id DESC LIMIT 5'),('Low Stock Alerts','SELECT name item,quantity qty,min_quantity minimum FROM products WHERE quantity<=min_quantity ORDER BY quantity LIMIT 5')]):
            grid.grid_columnconfigure(i,weight=1); box=self.card(grid);box.grid(row=0,column=i,sticky='nsew',padx=(0,6) if i==0 else (6,0),pady=5);self.label(box,title,14,'bold').pack(anchor='w',padx=12,pady=10)
            panel_rows=self.db.rows(sql)
            if not panel_rows:
                empty_text='No purchases recorded yet.' if title=='Recent Purchases' else 'No low-stock items right now.'
                self.label(box,empty_text,11,color=self.colors['muted']).pack(anchor='w',padx=12,pady=3)
            for r in panel_rows:
                display=dict(r)
                if 'date' in display:display['date']=self.format_date(display['date'])
                self.label(box,'  •  '+'  |  '.join(str(v) for v in display.values()),11,color=self.colors['muted']).pack(anchor='w',padx=12,pady=3)
        self.section(self.content,'Quick Actions')
        actions=[('＋ Add Product',self.add_product_dialog),('＋ Add Purchase',self.add_purchase_dialog),('☑ Shopping List',lambda:self.show_page('Shopping')),('⇄ Compare Prices',lambda:self.show_page('Stores')),('₹ Record Expense',self.add_expense_dialog),('▤ View Reports',lambda:self.show_page('Reports'))]
        row=ctk.CTkFrame(self.content,fg_color='transparent');row.pack(fill='x')
        for i,(txt,cmd) in enumerate(actions):row.grid_columnconfigure(i%3,weight=1);self.button(row,txt,cmd,True).grid(row=i//3,column=i%3,sticky='ew',padx=5,pady=5)
    def page_assistant(self):
        self.section(self.content,'Smart Household Assistant',[('↻ Refresh Insights',lambda:self.show_page('Assistant'))])
        products=self.db.rows('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.name'); insights=[]
        for p in products:
            if p['quantity']<=0:insights.append(('HIGH','Restock '+p['name'],f"Current stock is zero. Add at least {max(1,p['min_quantity']):g} {p['unit']} to your next list."))
            elif p['quantity']<=p['min_quantity']:insights.append(('MEDIUM','Low stock: '+p['name'],f"Only {p['quantity']:g} {p['unit']} remain against a minimum of {p['min_quantity']:g}. Suggested top-up: {p['min_quantity']-p['quantity']:g} {p['unit']}."))
        exp=self.db.rows('SELECT p.name,b.expiry_date,b.quantity FROM product_batches b JOIN products p ON p.id=b.product_id WHERE b.quantity>0 AND b.expiry_date IS NOT NULL')
        for b in exp:
            try:days=(date.fromisoformat(b['expiry_date'])-date.today()).days
            except ValueError:continue
            if days<0:
                insights.append(('HIGH','Expired stock: '+b['name'],f"Batch quantity {b['quantity']:g}; expired {abs(days)} day(s) ago. Do not consume this batch; record it as wastage."))
            elif days<=7:
                insights.append(('MEDIUM','Expiry attention: '+b['name'],f"Batch quantity {b['quantity']:g}; expiry date {self.format_date(b['expiry_date'])} (in {days} day(s)). Prioritise use before the expiry date."))
        today=date.today(); current=self.db.one("SELECT COALESCE(SUM(CAST(amount AS REAL)),0) n FROM expenses WHERE strftime('%Y-%m',expense_date)=?",(today.strftime('%Y-%m'),))['n']; previous=(today.replace(day=1)-timedelta(days=1)).strftime('%Y-%m')
        prev=self.db.one("SELECT COALESCE(SUM(CAST(amount AS REAL)),0) n FROM expenses WHERE strftime('%Y-%m',expense_date)=?",(previous,))['n']
        if prev>0 and current>prev*1.15:insights.append(('INFO','Spending is trending higher',f"Recorded spending is {((current/prev)-1)*100:.1f}% above the previous month. Review category totals and compare store prices."))
        if not insights:insights=[('INFO','Your household looks on track','No low-stock or near-expiry issues were detected from the current records. Keep purchase and expiry data up to date for better insights.')]
        for priority,title,desc in insights:
            box=self.card(self.content);box.pack(fill='x',pady=5);self.label(box,f'{priority}  •  {title}',14,'bold',self.colors['red'] if priority=='HIGH' else self.colors['orange'] if priority=='MEDIUM' else self.colors['green']).pack(anchor='w',padx=14,pady=(10,2));self.label(box,desc,12,color=self.colors['muted'],wraplength=950,justify='left').pack(anchor='w',padx=14,pady=(0,10))
    def page_notifications(self):
        self.db.generate_notifications();self.section(self.content,'Notification Centre',[('✓ Mark All Read',lambda:self.mark_all_read()),('↻ Refresh',lambda:self.show_page('Notifications'))])
        rows=self.db.rows('SELECT id,title,message,priority,is_read,created_at FROM notifications ORDER BY id DESC LIMIT 200')
        tree=self.table(self.content,['id','title','message','priority','is_read','created_at'],rows,15)
        if not rows:self.label(self.content,'No notifications yet. New stock, expiry and budget alerts will appear here.',11,color=self.colors['muted']).pack(anchor='w')
        self.button(self.content,'Mark selected as read',lambda:self.mark_selected_read(tree)).pack(anchor='e',pady=8)
    def mark_all_read(self):self.db.execute('UPDATE notifications SET is_read=1');self.show_page('Notifications')
    def mark_selected_read(self,tree):
        nid=self.selected_id(tree)
        if nid:self.db.execute('UPDATE notifications SET is_read=1 WHERE id=?',(nid,));self.show_page('Notifications')
    def page_reports(self):
        self.section(self.content,'Reports & Analytics',[('⇩ Export Expenses CSV',self.export_expenses),('▤ Export PDF Report',self.export_pdf_report)])
        total=self.db.one('SELECT COALESCE(SUM(CAST(amount AS REAL)),0) n FROM expenses')['n'];waste=self.db.one('SELECT COALESCE(SUM(quantity*CAST(unit_cost AS REAL)),0) n FROM waste_records')['n']
        self.stats(self.content,[('Lifetime Expenses',self.fmt(total),'All recorded expenses'),('Estimated Food Waste Cost',self.fmt(waste),'Recorded wastage'),('Products Tracked',str(self.db.one('SELECT COUNT(*) n FROM products')['n']),'Current catalogue'),('Purchases',str(self.db.one('SELECT COUNT(*) n FROM purchases')['n']),'Purchase records')])
        self.section(self.content,'Category-wise Spending')
        rows=self.db.rows('SELECT category,COUNT(*) transactions,SUM(CAST(amount AS REAL)) amount FROM expenses GROUP BY category ORDER BY amount DESC')
        for r in rows:r['amount']=self.fmt(r['amount'])
        self.table(self.content,['category','transactions','amount'],rows,8)
        self.section(self.content,'Most Purchased Products')
        rows=self.db.rows('SELECT p.name,SUM(pi.quantity) quantity,SUM(CAST(pi.line_total AS REAL)) spent FROM purchase_items pi JOIN products p ON p.id=pi.product_id GROUP BY p.id ORDER BY quantity DESC LIMIT 10')
        for r in rows:r['spent']=self.fmt(r['spent'])
        self.table(self.content,['name','quantity','spent'],rows,8)
        self.section(self.content,'Product Consumption — Last 30 Days')
        consumption=self.db.consumption_summary(30)
        for r in consumption:
            r['consumed']=f"{float(r['consumed']):g}"
            r['daily_rate']=f"{float(r['daily_rate']):.2f}"
            r['current_stock']=f"{float(r['current_stock']):g}"
        if consumption:self.table(self.content,['name','unit','consumed','daily_rate','current_stock'],consumption,8)
        else:self.label(self.content,'No consumption history is available yet.',11,color=self.colors['muted']).pack(anchor='w')
        self.section(self.content,'Active Budget Utilization')
        today=date.today().isoformat()
        active_budgets=self.db.rows('SELECT * FROM budgets WHERE start_date<=? AND end_date>=? ORDER BY category,name',(today,today))
        utilization=[]
        for budget in active_budgets:
            sql='SELECT COALESCE(SUM(CAST(amount AS REAL)),0) amount FROM expenses WHERE expense_date BETWEEN ? AND ?'
            params=[budget['start_date'],budget['end_date']]
            if budget['category']!='All':sql+=' AND category=?';params.append(budget['category'])
            spent=money(self.db.one(sql,params)['amount']); limit=money(budget['amount'])
            utilization.append({'budget':budget['name'],'category':budget['category'],'spent':self.fmt(spent),'limit':self.fmt(limit),'used':f'{float(spent/limit)*100:.1f}%' if limit>0 else '—'})
        if utilization:self.table(self.content,['budget','category','spent','limit','used'],utilization,6)
        else:self.label(self.content,'No active budgets cover today.',11,color=self.colors['muted']).pack(anchor='w')
        self.section(self.content,'Monthly Spending Trend')
        monthly=self.db.rows("SELECT strftime('%Y-%m',expense_date) month,SUM(CAST(amount AS REAL)) amount FROM expenses GROUP BY month ORDER BY month DESC LIMIT 12")
        monthly=list(reversed(monthly))
        if monthly:
            try:
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                fig=Figure(figsize=(8,2.7),dpi=95); ax=fig.add_subplot(111); ax.plot([x['month'] for x in monthly],[x['amount'] for x in monthly],marker='o'); ax.set_ylabel('Spend'); ax.tick_params(axis='x',rotation=30); fig.tight_layout()
                canvas=FigureCanvasTkAgg(fig,master=self.content);canvas.draw();canvas.get_tk_widget().pack(fill='x',pady=6)
            except Exception:self.label(self.content,'The monthly chart could not be rendered. Check the matplotlib installation and desktop display.',11,color=self.colors['muted']).pack(anchor='w')
        else:self.label(self.content,'No expense history is available for a chart yet.',11,color=self.colors['muted']).pack(anchor='w')
        # Additional analytical views: spending mix and current stock by category.
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            category=self.db.rows('SELECT category,SUM(CAST(amount AS REAL)) amount FROM expenses GROUP BY category HAVING amount>0 ORDER BY amount DESC LIMIT 8')
            if category:
                self.section(self.content,'Spending by Category')
                fig=Figure(figsize=(8,2.8),dpi=90); ax=fig.add_subplot(111); ax.bar([r['category'] for r in category],[r['amount'] for r in category]); ax.set_ylabel('Amount'); ax.tick_params(axis='x',rotation=25); fig.tight_layout()
                cv=FigureCanvasTkAgg(fig,master=self.content);cv.draw();cv.get_tk_widget().pack(fill='x',pady=5)
            stock=self.db.rows('SELECT COALESCE(c.name,"Uncategorised") category,SUM(p.quantity) quantity FROM products p LEFT JOIN categories c ON c.id=p.category_id GROUP BY category ORDER BY quantity DESC LIMIT 10')
            if stock:
                self.section(self.content,'Current Stock by Category')
                fig=Figure(figsize=(8,2.8),dpi=90); ax=fig.add_subplot(111); ax.barh([r['category'] for r in reversed(stock)],[r['quantity'] for r in reversed(stock)]); ax.set_xlabel('Stock quantity'); fig.tight_layout()
                cv=FigureCanvasTkAgg(fig,master=self.content);cv.draw();cv.get_tk_widget().pack(fill='x',pady=5)
        except Exception:self.label(self.content,'Additional charts could not be rendered. Check the matplotlib installation and desktop display.',10,color=self.colors['muted']).pack(anchor='w')
    def export_pdf_report(self):
        path=filedialog.asksaveasfilename(defaultextension='.pdf',filetypes=[('PDF','*.pdf')],initialfile='household_report.pdf')
        if not path:return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            c=canvas.Canvas(path,pagesize=A4); width,height=A4; y=height-48
            def pdf_safe(text):
                # Built-in Helvetica is Latin-1 only. Replace unsupported glyphs instead of aborting export.
                return str(text).encode('latin-1','replace').decode('latin-1')
            def page():
                nonlocal y
                c.showPage(); y=height-48
                c.setFont('Helvetica-Bold',14); c.drawString(42,y,pdf_safe('Smart Grocery & Household Manager - Report')); y-=24
            def line(text,bold=False):
                nonlocal y
                if y<55: page()
                c.setFont('Helvetica-Bold' if bold else 'Helvetica',9 if not bold else 11)
                c.drawString(44,y,pdf_safe(str(text)[:112])); y-=15
            c.setFont('Helvetica-Bold',17);c.drawString(42,y,pdf_safe('Smart Grocery & Household Manager'));y-=24
            line('Household summary report  |  Generated: '+datetime.now().strftime('%Y-%m-%d %H:%M'))
            total=self.db.one('SELECT COALESCE(SUM(CAST(amount AS REAL)),0) n FROM expenses')['n']
            waste=self.db.one('SELECT COALESCE(SUM(quantity*CAST(unit_cost AS REAL)),0) n FROM waste_records')['n']
            products=self.db.one('SELECT COUNT(*) n FROM products')['n']; purchases=self.db.one('SELECT COUNT(*) n FROM purchases')['n']
            line(f'Lifetime expenses: {self.fmt(total)}    |    Recorded waste cost: {self.fmt(waste)}',True)
            line(f'Products tracked: {products}    |    Purchase records: {purchases}')
            line('')
            sections=[
                ('Expense totals by category','SELECT category,COUNT(*) transactions,SUM(CAST(amount AS REAL)) amount FROM expenses GROUP BY category ORDER BY amount DESC',lambda r:f"{r['category']}  |  {r['transactions']} transactions  |  {self.fmt(r['amount'])}"),
                ('Monthly spending trend','SELECT strftime("%Y-%m",expense_date) month,SUM(CAST(amount AS REAL)) amount FROM expenses GROUP BY month ORDER BY month DESC LIMIT 12',lambda r:f"{r['month']}  |  {self.fmt(r['amount'])}"),
                ('Most purchased products','SELECT p.name,SUM(pi.quantity) quantity,SUM(CAST(pi.line_total AS REAL)) spent FROM purchase_items pi JOIN products p ON p.id=pi.product_id GROUP BY p.id ORDER BY quantity DESC LIMIT 15',lambda r:f"{r['name']}  |  quantity {float(r['quantity']):g}  |  {self.fmt(r['spent'])}"),
                ('Current low-stock products','SELECT name,quantity,min_quantity FROM products WHERE quantity<=min_quantity ORDER BY quantity',lambda r:f"{r['name']}  |  stock {float(r['quantity']):g}  |  minimum {float(r['min_quantity']):g}"),
                ('Recent purchases','SELECT purchase_date,total FROM purchases ORDER BY id DESC LIMIT 20',lambda r:f"{r['purchase_date']}  |  {self.fmt(r['total'])}"),
                ('Recorded wastage','SELECT p.name,w.quantity,w.reason,w.waste_date,w.unit_cost FROM waste_records w JOIN products p ON p.id=w.product_id ORDER BY w.waste_date DESC LIMIT 20',lambda r:f"{r['waste_date']}  |  {r['name']}  |  {float(r['quantity']):g}  |  {r['reason']}  |  {self.fmt(float(r['quantity'])*float(r['unit_cost']))}")]
            for title,sql,formatter in sections:
                line(title,True)
                rows=self.db.rows(sql)
                if not rows: line('No records available.')
                else:
                    for r in rows: line(formatter(r))
                line('')
            line('Product consumption - last 30 days',True)
            consumption=self.db.consumption_summary(30)
            if not consumption: line('No consumption history available.')
            for r in consumption:
                line(f"{r['name']} | consumed {float(r['consumed']):g} {r['unit']} | daily rate {float(r['daily_rate']):.2f} | stock {float(r['current_stock']):g}")
            line('')
            line('Active budget utilization',True)
            today=date.today().isoformat()
            budgets=self.db.rows('SELECT * FROM budgets WHERE start_date<=? AND end_date>=? ORDER BY category,name',(today,today))
            if not budgets: line('No active budgets.')
            for b in budgets:
                sql='SELECT COALESCE(SUM(CAST(amount AS REAL)),0) amount FROM expenses WHERE expense_date BETWEEN ? AND ?'
                params=[b['start_date'],b['end_date']]
                if b['category']!='All':sql+=' AND category=?';params.append(b['category'])
                spent=money(self.db.one(sql,params)['amount']); limit=money(b['amount'])
                line(f"{b['name']} ({b['category']}): {self.fmt(spent)} / {self.fmt(limit)} ({float(spent/limit)*100:.1f}%)" if limit>0 else f"{b['name']} ({b['category']}): {self.fmt(spent)} / {self.fmt(limit)} (not calculated)")
            c.save();messagebox.showinfo('PDF Report','Detailed PDF report exported successfully.')
        except ImportError:messagebox.showerror('PDF unavailable','Install reportlab using: pip install reportlab')
        except Exception as e:messagebox.showerror('PDF export failed',str(e))
    def export_expenses(self):
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if path:
            try:
                rows=self.db.rows('SELECT * FROM expenses')
                with open(path,'w',newline='',encoding='utf-8-sig') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['id']);w.writeheader();w.writerows([{k:spreadsheet_safe(v) for k,v in r.items()} for r in rows])
                messagebox.showinfo('Export','Expense report exported.')
            except Exception as e: messagebox.showerror('Export failed',str(e))
    def page_settings(self):
        self.section(self.content,'Application Settings')
        box=self.card(self.content);box.pack(fill='x',pady=6)
        self.label(box,'Appearance',15,'bold').pack(anchor='w',padx=15,pady=(14,4)); theme=ctk.CTkOptionMenu(box,values=['Light','Dark'],command=self.change_theme);theme.set(self.theme);theme.pack(anchor='w',padx=15,pady=5)
        self.label(box,'Currency display',15,'bold').pack(anchor='w',padx=15,pady=(14,4)); currency=ctk.CTkOptionMenu(box,values=list(CURRENCIES),command=self.change_currency);currency.set(self.currency);currency.pack(anchor='w',padx=15,pady=5)
        self.label(box,'Language',15,'bold').pack(anchor='w',padx=15,pady=(14,4)); language=ctk.CTkOptionMenu(box,values=list(LANGS),command=self.change_language);language.set(self.language);language.pack(anchor='w',padx=15,pady=5)
        self.label(box,'Budget alert thresholds (%)',15,'bold').pack(anchor='w',padx=15,pady=(14,4))
        thresholds=ctk.CTkEntry(box,width=260,placeholder_text='50,75,90,100');thresholds.pack(anchor='w',padx=15,pady=4);thresholds.insert(0,self.db.setting('budget_thresholds','50,75,90,100'))
        self.button(box,'Save alert thresholds',lambda:self.save_thresholds(thresholds.get())).pack(anchor='w',padx=15,pady=4)
        self.label(box,'Date format',15,'bold').pack(anchor='w',padx=15,pady=(14,4)); df=ctk.CTkOptionMenu(box,values=['%d-%m-%Y','%Y-%m-%d','%m/%d/%Y'],command=self.change_date_format);df.set(self.date_format);df.pack(anchor='w',padx=15,pady=5)
        row=ctk.CTkFrame(box,fg_color='transparent');row.pack(fill='x',padx=15,pady=15)
        self.button(row,'Create Database Backup',self.backup_database,True).pack(side='left',padx=4)
        self.button(row,'Restore Database Backup',self.restore_database).pack(side='left',padx=4)
        self.button(box,'Load Optional Sample Data',self.load_sample_data).pack(anchor='w',padx=15,pady=(2,8))
        self.label(box,'Sample data is optional and is never inserted automatically. Currency selection changes display formatting only; it does not perform foreign-exchange conversion.',10,color=self.colors['muted'],wraplength=850).pack(anchor='w',padx=15,pady=(0,12))
    def load_sample_data(self):
        if self.db.one('SELECT 1 FROM products LIMIT 1'):
            messagebox.showwarning('Sample data','Sample data can only be loaded into an empty inventory. It will not be mixed with your real records.')
            return
        if messagebox.askyesno('Load sample data','Load clearly labelled demonstration products and sample lists into this empty database?'):
            try:
                self.db.seed_demo_data()
                self.db.generate_notifications()
                messagebox.showinfo('Sample data','Demonstration data loaded. You can remove the database and start fresh at any time.')
                self.show_page('Inventory')
            except Exception as e:
                messagebox.showerror('Sample data failed',str(e))

    def save_thresholds(self,value):
        try:
            nums=sorted(set(int(x.strip()) for x in value.split(',') if x.strip()))
            if not nums or any(x not in {50,75,90,100} for x in nums):raise ValueError('Use the supported comma-separated thresholds: 50, 75, 90 and 100.')
            self.db.set_setting('budget_thresholds',','.join(map(str,nums)));messagebox.showinfo('Settings','Budget alert thresholds saved. They apply to future notification evaluations.')
        except Exception as e:messagebox.showerror('Invalid thresholds',str(e))
    def change_theme(self,x):
        self.theme=x
        self.db.set_setting('theme',x)
        # Let the option-menu callback finish and close its dropdown before the
        # settings page widgets are destroyed and recreated.
        self.after_idle(self.apply_theme)
    def change_currency(self,x):self.currency=x;self.db.set_setting('currency',x);self.show_page('Settings')
    def change_language(self,x):self.language=x;self.db.set_setting('language',x);self.show_page('Settings')
    def change_date_format(self,x):self.date_format=x;self.db.set_setting('date_format',x);self.show_page('Settings')
    def backup_database(self):
        path=filedialog.asksaveasfilename(defaultextension='.db',filetypes=[('SQLite database','*.db')],initialfile=f"smart_grocery_backup_{date.today().isoformat()}.db")
        if path:
            try:
                if Path(path).resolve()==self.db.path.resolve(): raise ValueError('Choose a different file name from the active database.')
                with self.db.connect() as c:
                    dest=sqlite3.connect(path)
                    try: c.backup(dest)
                    finally: dest.close()
                validate_backup(path)
                messagebox.showinfo('Backup','Database backup created and validated successfully.')
            except Exception as e:messagebox.showerror('Backup failed',str(e))
    def restore_database(self):
        path=filedialog.askopenfilename(filetypes=[('SQLite database','*.db'),('All files','*.*')])
        if not path:return
        try:
            if Path(path).resolve()==self.db.path.resolve():
                raise ValueError('The selected file is already the active database.')
            validate_backup(path)
            if not messagebox.askyesno('Restore','Restore this database? A safety backup will be created first.'):
                return
            safety_dir=ROOT/'backups'; safety_dir.mkdir(parents=True,exist_ok=True)
            stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            safety=safety_dir/f'pre_restore_{stamp}.db'
            try:
                with self.db.connect() as source_connection:
                    safety_connection=sqlite3.connect(safety)
                    try: source_connection.backup(safety_connection)
                    finally: safety_connection.close()
            except Exception:
                # A damaged current database must not prevent restoring a separately validated backup.
                logging.exception('SQLite backup API could not create the pre-restore safety copy; trying a raw file copy.')
                shutil.copy2(self.db.path,safety)
            temp_restore=self.db.path.with_suffix(self.db.path.suffix+'.restore_tmp')
            try:
                shutil.copy2(path,temp_restore)
                validate_backup(temp_restore)
                temp_restore.replace(self.db.path)
            finally:
                if temp_restore.exists(): temp_restore.unlink()
            messagebox.showinfo('Restore','Database restored successfully. The application will now close; reopen it to use the restored data.')
            self.destroy()
        except Exception as e:
            logging.exception('Database restore failed')
            messagebox.showerror('Restore failed',str(e))

    def page_help(self):
        self.section(self.content,'Help & Support')
        topics=[('Inventory','Add products, set minimum stock, update quantities and track stock status. Double-click an inventory row to edit it.'),('Purchases','Record a purchase to add stock, create a purchase record and create its linked expense in one transaction.'),('Shopping Lists','Create multiple lists, add products and track estimated item costs.'),('Price Comparison','Record observed package prices at different stores. Compare only compatible units and package quantities.'),('Expiry & FIFO','Enter expiry dates when creating purchase batches. The tracker orders batches by earliest expiry.'),('Expenses & Budgets','Record household expenses and create date-bounded budgets to track spending.'),('Smart Assistant','Recommendations are calculated from inventory levels, expiry batches and recorded expenses.'),('Settings','Theme, currency display, language and date-format preferences are saved locally. Currency switching does not convert values.'),('Backup & Restore','Create a database backup before major changes. Restore validates the selected SQLite database and creates a safety copy.')]
        for title,desc in topics:
            b=self.card(self.content);b.pack(fill='x',pady=5);self.label(b,title,14,'bold').pack(anchor='w',padx=14,pady=(9,2));self.label(b,desc,11,color=self.colors['muted'],wraplength=950,justify='left').pack(anchor='w',padx=14,pady=(0,9))

if __name__=='__main__':
    app=GroceryApp(); app.mainloop()
