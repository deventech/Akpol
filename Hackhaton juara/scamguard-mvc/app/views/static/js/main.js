// Klik contoh URL -> isi input lalu kirim form
document.querySelectorAll('[data-ex]').forEach(function (b) {
  b.addEventListener('click', function () {
    var f = document.querySelector('form[data-form]');
    f.querySelector('input').value = b.dataset.ex;
    f.submit();
  });
});
// Tombol berubah saat memproses
document.querySelectorAll('form.field').forEach(function (f) {
  f.addEventListener('submit', function () {
    var b = f.querySelector('button');
    b.textContent = 'Menganalisis...';
    b.disabled = true;
  });
});
