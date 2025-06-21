# 👻 GhostText

GhostText é uma ferramenta em Python que permite traduzir textos de jogos em tempo real, diretamente da tela. Ao pressionar um atalho, o programa captura uma imagem da tela (ou área selecionada), realiza OCR para extrair o texto, traduz e exibe a tradução sobre o jogo com um efeito de *blur*, criando uma segunda camada não intrusiva.

> 🔸 Projeto inspirado no [Game2Text](https://github.com/mathewthe2/Game2Text), com algumas abordagens próprias.  
> 🔸 Atualmente funcional, mas em pausa (Focarei em outros Projetos).  
> 🔸 Código aberto para quem quiser contribuir ou levar a ideia adiante!

---

## 🎮 Funcionalidades

- Captura da tela inteira ou seleção manual da área
- Extração de texto via OCR (atualmente usando EasyOCR)
- Tradução automática (GoogleTranslator via deep-translator)
- Sobreposição da tradução com efeito de desfoque (blur) no texto original

---

### Atalhos
- Ctrl + e (Trtaduz a Tela Inteira)
- Ctrl + Shift + e (Traduz apenas a área selecionada [Aperte enter para confirmar a seleção])

---

## 🧠 Ideias para o futuro

- Substituir o EasyOCR por PaddleOCR para melhorar a precisão
- Adicionar suporte a múltiplos idiomas e auto detecção
- Melhorar o posicionamento do texto traduzido
- Criar interface gráfica mais personalizável
- Atalhos de teclado configuráveis
