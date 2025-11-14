// static/app.js

let history = [];
let isGenerating = false;

// Elements
const sketchInput = document.getElementById("sketch-input");
const dropzone = document.getElementById("dropzone");
const previewContainer = document.getElementById("preview-container");
const sketchPreview = document.getElementById("sketch-preview");
const promptInput = document.getElementById("prompt-input");
const initialForm = document.getElementById("initial-form");
const initialError = document.getElementById("initial-error");
const btnGenerateInitial = document.getElementById("btn-generate-initial");
const initialButtonText = document.getElementById("initial-button-text");
const initialSpinner = document.getElementById("initial-spinner");

const conversationHistory = document.getElementById("conversation-history");
const conversationEmpty = document.getElementById("conversation-empty");
const continueForm = document.getElementById("continue-form");
const continuePromptInput = document.getElementById("continue-prompt");
const continueError = document.getElementById("continue-error");
const btnContinue = document.getElementById("btn-continue");

const btnExportJson = document.getElementById("btn-export-json");
const btnExportPdf = document.getElementById("btn-export-pdf");

// --- Helpers ------------------------------------------------------

function setInitialLoading(loading) {
  isGenerating = loading;
  if (btnGenerateInitial) {
    btnGenerateInitial.disabled = loading;
  }
  if (initialSpinner) {
    initialSpinner.classList.toggle("hidden", !loading);
  }
  if (initialButtonText) {
    initialButtonText.textContent = loading ? "Generating..." : "Generate";
  }
}

function setContinueLoading(loading) {
  if (btnContinue) {
    btnContinue.disabled = loading || history.length === 0;
  }
}

function showInitialError(msg) {
  if (!initialError) return;
  if (!msg) {
    initialError.classList.add("hidden");
    initialError.textContent = "";
  } else {
    initialError.textContent = msg;
    initialError.classList.remove("hidden");
  }
}

function showContinueError(msg) {
  if (!continueError) return;
  if (!msg) {
    continueError.classList.add("hidden");
    continueError.textContent = "";
  } else {
    continueError.textContent = msg;
    continueError.classList.remove("hidden");
  }
}

function renderHistory() {
  if (!conversationHistory) return;

  conversationHistory.innerHTML = "";

  if (!history.length) {
    if (conversationEmpty) {
      conversationHistory.appendChild(conversationEmpty);
      conversationEmpty.classList.remove("hidden");
    }
    if (btnContinue) {
      btnContinue.disabled = true;
    }
    return;
  }

  if (conversationEmpty) {
    conversationEmpty.classList.add("hidden");
  }
  if (btnContinue) {
    btnContinue.disabled = false;
  }

  history.forEach((turn) => {
    const wrapper = document.createElement("div");
    wrapper.className = "space-y-3";

    // User block
    const userRow = document.createElement("div");
    userRow.className = "flex items-start gap-3";

    const userAvatar = document.createElement("div");
    userAvatar.className =
      "h-9 w-9 rounded-full bg-blue-500 flex items-center justify-center text-xs font-bold";
    userAvatar.textContent = "U";

    const userBubble = document.createElement("div");
    userBubble.className =
      "bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 flex-1";
    userBubble.textContent = turn.prompt;

    userRow.appendChild(userAvatar);
    userRow.appendChild(userBubble);

    // Bot block
    const botRow = document.createElement("div");
    botRow.className = "flex items-start gap-3";

    const botAvatar = document.createElement("div");
    botAvatar.className =
      "h-9 w-9 rounded-full bg-pink-500 flex items-center justify-center text-xs font-bold";
    botAvatar.textContent = "AI";

    const botBubble = document.createElement("div");
    botBubble.className =
      "bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 flex-1 space-y-2";

    if (turn.outputImage) {
      const img = document.createElement("img");
      img.src = turn.outputImage;
      img.alt = "AI generated";
      img.className = "max-h-64 rounded-md border border-gray-700";
      botBubble.appendChild(img);
    }

    if (turn.modelResponseText) {
      const text = document.createElement("p");
      text.className = "text-sm text-gray-200";
      text.textContent = turn.modelResponseText;
      botBubble.appendChild(text);
    }

    botRow.appendChild(botAvatar);
    botRow.appendChild(botBubble);

    wrapper.appendChild(userRow);
    wrapper.appendChild(botRow);

    conversationHistory.appendChild(wrapper);
  });

  // Scroll to bottom
  conversationHistory.scrollTop = conversationHistory.scrollHeight;
}

// --- File upload / preview ---------------------------------------

function handleFile(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    showInitialError("Please upload a valid image file (PNG, JPG, etc.).");
    return;
  }
  showInitialError("");

  const reader = new FileReader();
  reader.onloadend = () => {
    if (previewContainer) previewContainer.classList.remove("hidden");
    if (sketchPreview) sketchPreview.src = reader.result;
  };
  reader.readAsDataURL(file);
}

if (sketchInput) {
  sketchInput.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    handleFile(file);
  });
}

if (dropzone) {
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("border-pink-500");
  });
  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("border-pink-500");
  });
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("border-pink-500");
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  });
}

// --- Initial form submit -----------------------------------------

if (initialForm) {
  initialForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    showInitialError("");

    const file = sketchInput?.files?.[0];
    const prompt = promptInput?.value.trim();

    if (!file) {
      showInitialError("Please upload a sketch.");
      return;
    }
    if (!prompt) {
      showInitialError("Please provide a description.");
      return;
    }

    setInitialLoading(true);

    try {
      const formData = new FormData();
      formData.append("sketch", file);
      formData.append("prompt", prompt);

      const res = await fetch("/api/initial", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to generate image.");
      }

      history.push({
        id: data.id,
        prompt: data.prompt,
        inputImage: data.inputImage,
        outputImage: data.outputImage,
        modelResponseText: data.modelResponseText,
        createdAt: data.createdAt,
      });

      renderHistory();
    } catch (err) {
      console.error(err);
      showInitialError(err.message || "Something went wrong.");
    } finally {
      setInitialLoading(false);
    }
  });
}

// --- Continue conversation ---------------------------------------

if (continueForm) {
  continueForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    showContinueError("");

    const prompt = continuePromptInput?.value.trim();
    if (!prompt) {
      showContinueError("Please enter a prompt.");
      return;
    }
    if (!history.length) {
      showContinueError("You need at least one generated image first.");
      return;
    }

    setContinueLoading(true);

    const lastTurn = history[history.length - 1];
    const lastImage = lastTurn.outputImage;

    try {
      const res = await fetch("/api/continue", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt,
          lastImage,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to generate image.");
      }

      history.push({
        id: data.id,
        prompt: data.prompt,
        inputImage: data.inputImage,
        outputImage: data.outputImage,
        modelResponseText: data.modelResponseText,
        createdAt: data.createdAt,
      });

      if (continuePromptInput) continuePromptInput.value = "";
      renderHistory();
    } catch (err) {
      console.error(err);
      showContinueError(err.message || "Something went wrong.");
    } finally {
      setContinueLoading(false);
    }
  });
}

// --- Export JSON -------------------------------------------------

if (btnExportJson) {
  btnExportJson.addEventListener("click", () => {
    if (!history.length) return;
    const blob = new Blob([JSON.stringify(history, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sketch_to_vision_conversation.json";
    a.click();
    URL.revokeObjectURL(url);
  });
}

// --- Export PDF (simple: capture conversation div) ----------------

if (btnExportPdf) {
  btnExportPdf.addEventListener("click", async () => {
    if (!history.length) return;
    if (!window.jspdf || !html2canvas || !conversationHistory) {
      alert("PDF export is not available.");
      return;
    }
    const { jsPDF } = window.jspdf;

    try {
      const canvas = await html2canvas(conversationHistory, {
        backgroundColor: "#111827",
        scale: 2,
      });
      const imgData = canvas.toDataURL("image/png");

      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();

      const imgWidth = pageWidth - 20;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      pdf.addImage(
        imgData,
        "PNG",
        10,
        10,
        imgWidth,
        Math.min(imgHeight, pageHeight - 20)
      );
      pdf.save("sketch_to_vision_conversation.pdf");
    } catch (err) {
      console.error(err);
      alert("Failed to export PDF.");
    }
  });
}

// --- Initial load: fetch history ---------------------------------

async function loadHistory() {
  if (!conversationHistory) return;
  try {
    const res = await fetch("/api/my_history");
    if (!res.ok) {
      throw new Error("Failed to load history.");
    }
    const data = await res.json();
    history = data || [];
    renderHistory();
  } catch (err) {
    console.error(err);
  }
}

loadHistory();
