/*
 * forms.js: transaction helpers (vanilla ES6).
 *  - Paste an M-Pesa SMS, send it to the server parser, then open a
 *    pre-filled form for the student to review before saving.
 *  - Suggest a category from the description as the student types.
 *  - Show only the relevant date inputs on the report form.
 */
(function () {
  "use strict";

  function csrfToken(form) {
    const input = form.querySelector("input[name='csrfmiddlewaretoken']");
    return input ? input.value : "";
  }

  function formatKsh(value) {
    const number = Number(value);
    return "KSh " + number.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  /* ---------- M-Pesa paste parser ---------- */
  const pasteForm = document.querySelector("[data-paste-form]");
  if (pasteForm) {
    const result = pasteForm.querySelector("[data-paste-result]");

    pasteForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      const message = pasteForm.querySelector("textarea").value;
      result.replaceChildren(el("p", "muted", "Reading message…"));

      try {
        const response = await fetch(pasteForm.dataset.parseUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken(pasteForm) },
          body: JSON.stringify({ message: message }),
        });
        const data = await response.json();
        result.replaceChildren();

        if (!data.ok) {
          result.appendChild(el("div", "alert alert--warning", data.error));
          return;
        }

        const t = data.transaction;
        const box = el("div", "alert alert--success");
        const content = el("div");
        const kindLabel = t.kind === "income" ? "Income" : t.kind === "expense" ? "Expense" : "Cash withdrawal";
        content.appendChild(el("p", "", kindLabel + " of " + formatKsh(t.amount) + " on " + t.date + "."));
        if (t.description) content.appendChild(el("p", "small", t.description));
        if (t.category_name) content.appendChild(el("p", "small", "Suggested category: " + t.category_name));
        t.warnings.forEach(function (w) {
          content.appendChild(el("p", "small", w));
        });

        if (t.kind === "income" || t.kind === "expense") {
          const base = t.kind === "income" ? pasteForm.dataset.incomeUrl : pasteForm.dataset.expenseUrl;
          const params = new URLSearchParams({
            amount: t.amount,
            date: t.date,
            description: t.description,
            reference: t.reference,
          });
          if (t.category_id) params.set("category", t.category_id);
          const link = el("a", "btn btn--primary btn--sm", "Review and save");
          link.href = base + "?" + params.toString();
          content.appendChild(link);
        }
        box.appendChild(content);
        result.appendChild(box);
      } catch (error) {
        result.replaceChildren(el("div", "alert alert--danger", "Could not reach the server. Check your connection."));
      }
    });
  }

  /* ---------- Category suggestion while typing ---------- */
  const txForm = document.querySelector("form[data-suggest-url]");
  if (txForm) {
    const fieldName = txForm.dataset.categoryField;
    const select = txForm.querySelector("select[name='" + fieldName + "']");
    const description = txForm.querySelector("input[name='description']");
    const hint = txForm.querySelector("[data-suggest-hint]");
    let timer = null;
    let userChoseCategory = select && select.value !== "";

    if (select) {
      select.addEventListener("change", function () {
        userChoseCategory = true;
      });
    }

    if (select && description && hint) {
      description.addEventListener("input", function () {
        window.clearTimeout(timer);
        const text = description.value.trim();
        if (text.length < 3 || userChoseCategory) {
          hint.hidden = true;
          return;
        }
        timer = window.setTimeout(async function () {
          try {
            const url = txForm.dataset.suggestUrl + "&q=" + encodeURIComponent(text);
            const response = await fetch(url, { credentials: "same-origin" });
            const data = await response.json();
            if (data.category_id && !userChoseCategory) {
              select.value = String(data.category_id);
              hint.textContent = "Suggested category: " + data.category_name + " (you can change it).";
              hint.hidden = false;
            }
          } catch (error) {
            hint.hidden = true;
          }
        }, 350);
      });
    }
  }

  /* ---------- Report form: show only relevant inputs ---------- */
  const reportForm = document.querySelector("[data-report-form]");
  if (reportForm) {
    const kind = reportForm.querySelector("select[name='kind']");
    const groups = {
      month: ["month"],
      custom: ["start", "end"],
      semester: [],
    };
    function update() {
      ["month", "start", "end"].forEach(function (name) {
        const input = reportForm.querySelector("[name='" + name + "']");
        if (!input) return;
        const field = input.closest(".field");
        if (field) field.hidden = groups[kind.value].indexOf(name) === -1;
      });
    }
    if (kind) {
      kind.addEventListener("change", update);
      update();
    }
  }
})();
