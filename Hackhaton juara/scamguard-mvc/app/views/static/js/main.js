// Klik contoh URL -> isi input lalu kirim form
document.querySelectorAll('[data-ex]').forEach(function (b) {
  b.addEventListener('click', function () {
    var f = document.querySelector('form[data-form]');
    f.querySelector('input').value = b.dataset.ex;
    f.submit();
  });
});
