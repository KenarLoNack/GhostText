"""
OCR com EasyOCR + Tradução com Deep Translator + Overlay em Tkinter (Windows)

Melhorias:
1. Limpeza adequada das regiões entre detecções
2. Atualização completa da janela de textos
3. Controle de tamanho de fonte
"""

import tkinter as tk
from tkinter import Canvas, Toplevel, Text, Scrollbar, Frame, Button, Label, Entry
from PIL import ImageGrab, Image, ImageTk, ImageFilter
import numpy as np
import cv2
import easyocr
from deep_translator import GoogleTranslator
import keyboard
import threading
import warnings
import math

# Suprime avisos específicos do torch
warnings.filterwarnings("ignore", message=".*'pin_memory'.*")


class OCRTranslateOverlay:
    def __init__(self):
        # Inicializa o leitor EasyOCR para inglês
        self.ocr_reader = easyocr.Reader(['en'], gpu=False)
        # Inicializa o tradutor Deep Translator (GoogleTranslator via deep-translator)
        self.translator = GoogleTranslator(source='en', target='pt')

        # Lista para armazenar dados das regiões detectadas
        self.regions = []
        self.hud_visible = True  # Estado inicial da HUD

        # Cria janela principal (HUD)
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        self.root.config(bg='black')
        # Define a cor preta como transparente
        self.root.attributes('-transparentcolor', 'black')

        # Cria Canvas para desenhar borda e sobreposições
        self.canvas = Canvas(self.root, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Borda ao redor da tela (inicialmente vermelha)
        self.border_width = 3
        self.border_color = 'red'
        self.border_items = []
        self._create_border()

        # Frame de controles (botões) na parte inferior centralizada
        self.controls = Frame(self.root, bg='black', bd=0)
        self.controls.place(relx=0.5, rely=0.95, anchor='center')

        btn_show_texts = Button(self.controls, text="Mostrar Textos", command=self.open_text_window,
                                bg='gray20', fg='white', bd=0, padx=10, pady=5)
        btn_show_texts.pack(side=tk.LEFT, padx=5)

        btn_remove = Button(self.controls, text="Remover Overlay", command=self.clear_overlays,
                            bg='gray20', fg='white', bd=0, padx=10, pady=5)
        btn_remove.pack(side=tk.LEFT, padx=5)

        btn_toggle_border = Button(self.controls, text="Toggle Borda", command=self._toggle_border,
                                   bg='gray20', fg='white', bd=0, padx=10, pady=5)
        btn_toggle_border.pack(side=tk.LEFT, padx=5)

        btn_toggle_hud = Button(self.controls, text="Esconder HUD", command=self.toggle_hud,
                                bg='gray20', fg='white', bd=0, padx=10, pady=5)
        btn_toggle_hud.pack(side=tk.LEFT, padx=5)

        btn_exit = Button(self.controls, text="Fechar", command=self.close_program,
                          bg='gray20', fg='white', bd=0, padx=10, pady=5)
        btn_exit.pack(side=tk.LEFT, padx=5)

        # Janela de textos
        self.text_window = None
        self.font_size_var = tk.StringVar(
            value="12")  # Tamanho padrão da fonte

        # Variáveis para seleção de área
        self.selecting_area = False
        self.selection_start = None
        self.selection_rect = None
        self.selection_canvas = None
        self.selection_bbox = None
        self.selection_window = None

        # Configura atalhos de teclado
        keyboard.add_hotkey(
            'ctrl+e', lambda: threading.Thread(target=self.scan_and_overlay).start())
        keyboard.add_hotkey(
            'ctrl+q', lambda: threading.Thread(target=self.clear_overlays).start())
        keyboard.add_hotkey(
            'ctrl+shift+e', self.start_area_selection)
        keyboard.add_hotkey(
            'ctrl+h', self.toggle_hud)

    def _create_border(self):
        """Desenha a borda ao redor da tela."""
        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()

        # Topo
        self.border_items.append(
            self.canvas.create_rectangle(0, 0, width, self.border_width,
                                         fill=self.border_color, outline='')
        )
        # Base
        self.border_items.append(
            self.canvas.create_rectangle(0, height - self.border_width, width, height,
                                         fill=self.border_color, outline='')
        )
        # Lado esquerdo
        self.border_items.append(
            self.canvas.create_rectangle(0, 0, self.border_width, height,
                                         fill=self.border_color, outline='')
        )
        # Lado direito
        self.border_items.append(
            self.canvas.create_rectangle(width - self.border_width, 0, width, height,
                                         fill=self.border_color, outline='')
        )

    def _change_border_color(self, color):
        """Altera a cor da borda."""
        self.border_color = color
        for item in self.border_items:
            self.canvas.itemconfig(item, fill=color)

    def _toggle_border(self):
        """Alterna visibilidade da borda."""
        current_state = self.canvas.itemcget(self.border_items[0], 'state')
        new_state = tk.HIDDEN if current_state == tk.NORMAL else tk.NORMAL
        for item in self.border_items:
            self.canvas.itemconfig(item, state=new_state)

    def toggle_hud(self):
        """Alterna visibilidade completa da HUD (borda e controles)."""
        self.hud_visible = not self.hud_visible

        # Atualiza texto do botão
        for widget in self.controls.winfo_children():
            if isinstance(widget, Button) and widget.cget("text") in ["Esconder HUD", "Mostrar HUD"]:
                widget.config(
                    text="Mostrar HUD" if not self.hud_visible else "Esconder HUD")

        # Alterna visibilidade dos elementos
        new_state = tk.NORMAL if self.hud_visible else tk.HIDDEN
        for item in self.border_items:
            self.canvas.itemconfig(item, state=new_state)

        # Mostra ou esconde o frame de controles
        if self.hud_visible:
            self.controls.place(relx=0.5, rely=0.95, anchor='center')
        else:
            self.controls.place_forget()

    def _take_screenshot(self, bbox=None):
        """Captura a tela ou uma área específica."""
        if bbox:
            # Verifica se a área de seleção é válida
            x1, y1, x2, y2 = bbox
            if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
                return None
            return ImageGrab.grab(bbox=bbox)
        else:
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            return ImageGrab.grab(bbox=(0, 0, width, height))

    def _get_brightness(self, rgb):
        """Calcula o brilho de uma cor RGB (0-255)."""
        r, g, b = rgb
        return math.sqrt(0.299 * r**2 + 0.587 * g**2 + 0.114 * b**2)

    def _approximate_text_color(self, img_region):
        """
        Aproxima a cor do texto original extraindo pixels escuros do centro da região.
        Retorna a cor do texto e a cor do contorno apropriada.
        """
        np_img = np.array(img_region.convert('RGB'))
        h, w, _ = np_img.shape

        # Recorta uma área central
        x1 = int(w * 0.4)
        y1 = int(h * 0.4)
        x2 = int(w * 0.6)
        y2 = int(h * 0.6)
        central = np_img[y1:y2, x1:x2, :]

        # Converte para escala de cinza para encontrar pixels escuros
        gray = cv2.cvtColor(central, cv2.COLOR_RGB2GRAY)
        mask = gray < 128

        if np.count_nonzero(mask) == 0:
            # Se não houver pixels escuros, usamos preto
            text_color = '#000000'
            avg_color = (0, 0, 0)
        else:
            selected = central[mask]
            avg_color = np.mean(selected, axis=0).astype(int)
            text_color = '#{:02x}{:02x}{:02x}'.format(
                avg_color[0], avg_color[1], avg_color[2])

        # Determina se precisamos de contorno claro ou escuro
        brightness = self._get_brightness(avg_color)
        outline_color = '#ffffff' if brightness < 127 else '#000000'

        # Garantir que retorna apenas 2 valores
        return (text_color, outline_color)

    def start_area_selection(self):
        """Inicia o modo de seleção de área com o mouse."""
        # Mostra HUD se estiver oculta
        if not self.hud_visible:
            self.toggle_hud()

        if self.selecting_area:
            return

        self.selecting_area = True
        self._change_border_color('yellow')

        # Cria uma nova janela transparente para a seleção
        self.selection_window = Toplevel(self.root)
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-topmost', True)
        self.selection_window.overrideredirect(True)
        self.selection_window.attributes('-alpha', 0.3)
        self.selection_window.config(bg='black')

        # Cria canvas para desenhar a seleção
        self.selection_canvas = Canvas(
            self.selection_window, bg='black', highlightthickness=0)
        self.selection_canvas.pack(fill=tk.BOTH, expand=True)
        self.selection_canvas.config(cursor="crosshair")

        # Configura eventos do mouse
        self.selection_canvas.bind("<ButtonPress-1>", self.on_selection_start)
        self.selection_canvas.bind("<B1-Motion>", self.on_selection_drag)
        self.selection_canvas.bind("<ButtonRelease-1>", self.on_selection_end)

        # Configura atalho para confirmar com Enter
        keyboard.add_hotkey('enter', self.confirm_selection)

    def on_selection_start(self, event):
        """Inicia a seleção de área."""
        self.selection_start = (event.x_root, event.y_root)
        self.selection_rect = self.selection_canvas.create_rectangle(
            event.x_root, event.y_root, event.x_root, event.y_root,
            outline='red', width=2, dash=(4, 4)
        )

    def on_selection_drag(self, event):
        """Atualiza a seleção durante o arrasto do mouse."""
        if self.selection_rect:
            self.selection_canvas.coords(
                self.selection_rect,
                self.selection_start[0], self.selection_start[1],
                event.x_root, event.y_root
            )

    def on_selection_end(self, event):
        """Finaliza a seleção e define a área."""
        if self.selection_rect:
            # Obtém coordenadas da área selecionada
            x1, y1 = self.selection_start
            x2, y2 = event.x_root, event.y_root
            self.selection_bbox = (min(x1, x2), min(
                y1, y2), max(x1, x2), max(y1, y2))

    def confirm_selection(self):
        """Confirma a seleção e processa a área."""
        if self.selecting_area and self.selection_bbox:
            # Fecha a janela de seleção
            self.selection_window.destroy()
            self.selecting_area = False
            self._change_border_color('red')

            # Remove o hotkey de confirmação
            keyboard.remove_hotkey('enter')

            # Processa a área selecionada
            threading.Thread(target=self.scan_and_overlay,
                             args=(self.selection_bbox,)).start()
        elif self.selecting_area:
            # Se não houver seleção, apenas cancela
            self.selection_window.destroy()
            self.selecting_area = False
            self._change_border_color('red')
            keyboard.remove_hotkey('enter')

    def scan_and_overlay(self, bbox=None):
        """Captura tela, executa OCR, traduz e aplica blur+texto traduzido."""
        # Mostra HUD se estiver oculta
        if not self.hud_visible:
            self.toggle_hud()

        # Altera borda para verde durante processamento
        self._change_border_color('green')

        try:
            # Limpa overlays anteriores e regiões
            self.clear_overlays()

            # Captura a tela (toda ou área específica)
            screenshot = self._take_screenshot(bbox)

            # Verifica se a captura foi bem sucedida
            if screenshot is None:
                print("Erro: Área de seleção inválida!")
                return

            # Executa OCR com EasyOCR - detecta blocos de texto completos
            ocr_results = self.ocr_reader.readtext(
                np.array(screenshot), detail=1, paragraph=True)

            # Determinar offset (se for uma área recortada)
            x_offset = bbox[0] if bbox else 0
            y_offset = bbox[1] if bbox else 0

            # Coleta todos os textos primeiro
            all_texts = []
            regions_data = []
            for res in ocr_results:
                # Versão mais recente do EasyOCR retorna (bbox, text) ou (bbox, text, confidence)
                if len(res) == 3:
                    bbox_pts, orig_text, confidence = res
                elif len(res) == 2:
                    bbox_pts, orig_text = res
                    confidence = 1.0  # Assume confiança máxima
                else:
                    continue

                if confidence < 0.5 or orig_text.strip() == '':
                    continue

                xs = [int(pt[0]) for pt in bbox_pts]
                ys = [int(pt[1]) for pt in bbox_pts]
                x, y = min(xs), min(ys)
                w, h = max(xs) - x, max(ys) - y

                # Ajusta para coordenadas absolutas da tela
                x_abs = x + x_offset
                y_abs = y + y_offset

                region = screenshot.crop((x, y, x + w, y + h))
                text_color, outline_color = self._approximate_text_color(
                    region)

                all_texts.append(orig_text)
                regions_data.append(
                    (x_abs, y_abs, w, h, region, text_color, outline_color, orig_text))

            # Traduz todos os textos de uma vez (blocos completos)
            translations = []
            for text in all_texts:
                try:
                    translations.append(self.translator.translate(text))
                except Exception as e:
                    print(f"Erro na tradução: {e}")
                    translations.append(text)

            # Aplica blur e texto traduzido
            for i, (translation, data) in enumerate(zip(translations, regions_data)):
                x_abs, y_abs, w, h, region, text_color, outline_color, orig_text = data

                # Aplica blur na região
                blurred = region.filter(ImageFilter.GaussianBlur(radius=5))
                blurred_tk = ImageTk.PhotoImage(blurred)

                # Desenha blur no Canvas
                blur_item = self.canvas.create_image(
                    x_abs, y_abs, anchor=tk.NW, image=blurred_tk, tags="overlay")

                # Desenha contorno para melhor legibilidade
                for dx, dy in [(1, 1), (1, -1), (-1, 1), (-1, -1), (0, 1), (0, -1), (1, 0), (-1, 0)]:
                    self.canvas.create_text(
                        x_abs + 2 + dx, y_abs + 2 + dy,
                        anchor=tk.NW,
                        text=translation,
                        fill=outline_color,
                        font=('Arial', int(self.font_size_var.get())),
                        width=w-4,  # Limita a largura à área do texto original
                        tags="overlay"
                    )

                # Desenha texto traduzido dentro da área original
                text_item = self.canvas.create_text(
                    x_abs + 2, y_abs + 2,
                    anchor=tk.NW,
                    text=translation,
                    fill=text_color,
                    font=('Arial', int(self.font_size_var.get())),
                    width=w-4,  # Limita a largura à área do texto original
                    tags="overlay"
                )

                # Armazena dados
                self.regions.append({
                    'bbox': (x_abs, y_abs, w, h),
                    'orig_text': orig_text,
                    'translation': translation,
                    'text_color': text_color,
                    'outline_color': outline_color,
                    'blurred_pil': blurred,  # Armazena a imagem borrada (PIL)
                    'blur_img': blurred_tk,
                    'text_item': text_item
                })

            # Mantém referências às imagens
            self.canvas.blur_images = [r['blur_img'] for r in self.regions]

            # Atualiza janela de textos se estiver aberta
            if self.text_window and tk.Toplevel.winfo_exists(self.text_window):
                self.update_text_window()

        except Exception as e:
            print(f"Erro durante o processamento: {e}")
        finally:
            # Restaura cor da borda após processamento
            self._change_border_color('red')

    def clear_overlays(self):
        """Remove todos os itens de overlay do Canvas, mantendo os textos na janela."""
        # Mostra HUD se estiver oculta
        if not self.hud_visible:
            self.toggle_hud()

        self.canvas.delete("overlay")
        self.regions.clear()  # Limpa completamente a lista de regiões

        # Atualiza janela de textos sem fechá-la
        if self.text_window and tk.Toplevel.winfo_exists(self.text_window):
            self.update_text_window()

    def open_text_window(self):
        """Abre janela flutuante com textos detectados e traduzidos."""
        # Mostra HUD se estiver oculta
        if not self.hud_visible:
            self.toggle_hud()

        if self.text_window and tk.Toplevel.winfo_exists(self.text_window):
            self.text_window.lift()
            return

        # Cria nova janela
        self.text_window = Toplevel(self.root)
        self.text_window.title("Textos Detectados / Traduzidos")
        self.text_window.attributes('-topmost', True)
        self.text_window.resizable(True, True)

        # Frame principal vertical
        main_frame = Frame(self.text_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Texto Detectado
        lbl_detected = Label(main_frame, text="Texto Detectado:")
        lbl_detected.pack(anchor='w')

        frame_detected = Frame(main_frame)
        frame_detected.pack(fill=tk.X, padx=5, pady=5)
        self.txt_detected = Text(
            frame_detected, width=80, height=10, wrap='word')
        self.txt_detected.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_det = Scrollbar(frame_detected, command=self.txt_detected.yview)
        scroll_det.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_detected.config(yscrollcommand=scroll_det.set)

        # Texto Traduzido
        lbl_translated = Label(main_frame, text="Texto Traduzido:")
        lbl_translated.pack(anchor='w')

        frame_translated = Frame(main_frame)
        frame_translated.pack(fill=tk.X, padx=5, pady=5)
        self.txt_translated = Text(
            frame_translated, width=80, height=10, wrap='word')
        self.txt_translated.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_trad = Scrollbar(
            frame_translated, command=self.txt_translated.yview)
        scroll_trad.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_translated.config(yscrollcommand=scroll_trad.set)

        # Botões
        btn_frame = Frame(main_frame)
        btn_frame.pack(pady=10)

        btn_retraduzir = Button(btn_frame, text="Retraduzir Selecionados", command=self.retranslate_selected,
                                bg='gray20', fg='white', bd=0, padx=10, pady=5)
        btn_retraduzir.pack(side=tk.LEFT, padx=5)

        btn_apply = Button(btn_frame, text="Aplicar Overlay", command=self.apply_texts,
                           bg='gray20', fg='white', bd=0, padx=10, pady=5)
        btn_apply.pack(side=tk.LEFT, padx=5)

        # Controle de tamanho de fonte
        font_frame = Frame(main_frame)
        font_frame.pack(pady=5)

        Label(font_frame, text="Tamanho da Fonte:").pack(side=tk.LEFT, padx=5)
        self.font_size_var = tk.StringVar(value="12")  # Valor padrão
        self.font_size_entry = Entry(
            font_frame, textvariable=self.font_size_var, width=5)
        self.font_size_entry.pack(side=tk.LEFT, padx=5)
        btn_apply_font = Button(font_frame, text="Aplicar Tamanho", command=self.apply_font_size,
                                bg='gray20', fg='white', bd=0, padx=5, pady=2)
        btn_apply_font.pack(side=tk.LEFT, padx=5)

        btn_close = Button(btn_frame, text="Fechar", command=self.text_window.destroy,
                           bg='gray20', fg='white', bd=0, padx=10, pady=5)
        btn_close.pack(side=tk.LEFT, padx=5)

        # Preenche com os textos atuais
        self.update_text_window()

    def update_text_window(self):
        """Atualiza o conteúdo da janela de textos."""
        if not self.text_window or not tk.Toplevel.winfo_exists(self.text_window):
            return

        # Limpa completamente as caixas de texto
        self.txt_detected.delete("1.0", tk.END)
        self.txt_translated.delete("1.0", tk.END)

        # Preenche com os textos atuais
        for region in self.regions:
            self.txt_detected.insert(tk.END, region['orig_text'] + "\n\n")
            self.txt_translated.insert(tk.END, region['translation'] + "\n\n")

    def retranslate_selected(self):
        """Retraduz os textos selecionados na janela de edição."""
        # Obtém o texto editado
        edited_text = self.txt_detected.get(
            "1.0", tk.END).strip().split("\n\n")

        # Atualiza traduções
        self.txt_translated.delete("1.0", tk.END)

        for idx, orig in enumerate(edited_text):
            if idx >= len(self.regions) or not orig.strip():
                continue

            try:
                new_translation = self.translator.translate(orig)
            except Exception as e:
                print(f"Erro na retradução: {e}")
                new_translation = orig

            self.regions[idx]['translation'] = new_translation
            self.txt_translated.insert(tk.END, new_translation + "\n\n")

    def apply_texts(self):
        """Aplica os textos editados como overlay na tela (com blur)."""
        # Mostra HUD se estiver oculta
        if not self.hud_visible:
            self.toggle_hud()

        # Limpa overlays anteriores
        self.canvas.delete("overlay")

        # Aplica os textos atuais com blur
        for region in self.regions:
            x_abs, y_abs, w, h = region['bbox']
            translation = region['translation']
            text_color = region['text_color']
            outline_color = region['outline_color']
            blurred_pil = region['blurred_pil']

            # Recria a imagem borrada
            blurred_tk = ImageTk.PhotoImage(blurred_pil)

            # Desenha blur no Canvas
            blur_item = self.canvas.create_image(
                x_abs, y_abs, anchor=tk.NW, image=blurred_tk, tags="overlay")

            # Desenha contorno para melhor legibilidade
            for dx, dy in [(1, 1), (1, -1), (-1, 1), (-1, -1), (0, 1), (0, -1), (1, 0), (-1, 0)]:
                self.canvas.create_text(
                    x_abs + 2 + dx, y_abs + 2 + dy,
                    anchor=tk.NW,
                    text=translation,
                    fill=outline_color,
                    font=('Arial', int(self.font_size_var.get())),
                    width=w-4,
                    tags="overlay"
                )

            # Desenha texto traduzido dentro da área original
            text_item = self.canvas.create_text(
                x_abs + 2, y_abs + 2,
                anchor=tk.NW,
                text=translation,
                fill=text_color,
                font=('Arial', int(self.font_size_var.get())),
                width=w-4,
                tags="overlay"
            )

            # Atualiza referências
            region['blur_img'] = blurred_tk
            region['text_item'] = text_item

    def apply_font_size(self):
        """Atualiza o tamanho da fonte para todos os overlays."""
        try:
            # Tenta converter para inteiro
            size = int(self.font_size_var.get())
            if size <= 0:
                raise ValueError("Tamanho deve ser positivo")

            # Reaplica os overlays com novo tamanho
            self.apply_texts()
        except ValueError:
            print("Tamanho de fonte inválido. Use um número inteiro positivo.")

    def close_program(self):
        """Encerra o programa e limpa atalhos."""
        keyboard.clear_all_hotkeys()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = OCRTranslateOverlay()
    app.run()
