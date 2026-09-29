// Chat send forms: no double send, Enter sends, Shift+Enter adds a new line.
// Plain JS, no framework. The forms are normal POST forms and work without it.
(function () {
  'use strict';

  var forms = document.querySelectorAll('form[data-chat-form]');

  forms.forEach(function (form) {
    var button = form.querySelector('button[type="submit"]');
    var box = form.querySelector('textarea');
    var idleText = button.textContent;
    var sending = false;

    function reset() {
      sending = false;
      button.disabled = false;
      button.textContent = idleText;
    }

    form.addEventListener('submit', function (event) {
      if (sending) {
        event.preventDefault();
        return;
      }
      sending = true;
      // Disabling here does not stop this submit. It stops the next one.
      button.disabled = true;
      button.textContent = button.dataset.waitingText || 'Waiting for reply…';
    });

    if (box) {
      box.addEventListener('keydown', function (event) {
        // Shift+Enter adds a new line. Enter while an input method is
        // composing text (e.g. Japanese) picks a word, so it must not send.
        if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) {
          return;
        }
        event.preventDefault();
        if (sending || !box.value.trim()) {
          return;
        }
        // requestSubmit runs the browser's checks and our submit handler.
        if (form.requestSubmit) {
          form.requestSubmit(button);
        } else {
          button.click();
        }
      });
    }

    // Back/forward can restore this page from the browser's cache with the
    // button still disabled. Turn it back on.
    window.addEventListener('pageshow', function (event) {
      if (event.persisted) {
        reset();
      }
    });
  });
})();
