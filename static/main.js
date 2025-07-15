document.addEventListener('submit', function(e){
  if (e.target.matches('form[action="/email"]')) {
    const btn = e.target.querySelector('button');
    const email = e.target.email.value;
    if (!/.+@.+\..+/.test(email)) {
      alert("Enter a valid email");
      e.preventDefault();
      return;
    }
    btn.disabled = true;
    btn.textContent = 'Sending...';
  }
});
