document.addEventListener('DOMContentLoaded', () => {
    const currentYearEl = document.getElementById('currentYear');
    if (currentYearEl) {
        currentYearEl.textContent = new Date().getFullYear();
    }

    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    const navbarCollapse = document.getElementById('navbarNav');
    const bsCollapse = navbarCollapse && window.bootstrap
        ? new bootstrap.Collapse(navbarCollapse, { toggle: false })
        : null;
    const contactForm = document.getElementById('contactForm');
    const contactStatus = document.getElementById('contactStatus');
    const contactNameInput = document.getElementById('name');
    const phoneInput = document.getElementById('phone');

    function setActiveNavLink(link) {
        navLinks.forEach(nav => nav.classList.remove('active'));
        if (link) {
            link.classList.add('active');
        }
    }

    function focusContactName() {
        if (!contactNameInput) return;
        try {
            contactNameInput.focus({ preventScroll: true });
        } catch (error) {
            contactNameInput.focus();
        }
    }

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', (e) => {
            e.preventDefault();

            const targetId = anchor.getAttribute('href');
            if (targetId === '#') return;

            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

            if (anchor.classList.contains('nav-link')) {
                setActiveNavLink(anchor);
            }

            if (bsCollapse && navbarCollapse.classList.contains('show')) {
                bsCollapse.hide();
            }

            if (targetId === '#contato') {
                focusContactName();
            }
        });
    });

    if (contactForm && contactStatus) {
        contactForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            contactStatus.textContent = 'Enviando sua mensagem...';
            contactStatus.className = 'text-center mt-3 text-info';

            const formData = new FormData(contactForm);
            const csrfToken = formData.get('csrfmiddlewaretoken');

            try {
                const response = await fetch(contactForm.action, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken },
                    body: formData,
                });

                const data = await response.json();

                if (!response.ok || !data.success) {
                    contactStatus.textContent = data.error || 'Não foi possível enviar sua mensagem.';
                    contactStatus.className = 'text-center mt-3 text-danger';
                    return;
                }

                contactStatus.textContent = 'Mensagem enviada com sucesso! Em breve entraremos em contato.';
                contactStatus.className = 'text-center mt-3 text-success';
                contactForm.reset();
                if (contactNameInput) {
                    contactNameInput.focus();
                }
            } catch (error) {
                contactStatus.textContent = 'Ocorreu um erro ao enviar. Tente novamente em instantes.';
                contactStatus.className = 'text-center mt-3 text-danger';
            }
        });
    }

    if (window.location.hash === '#contato') {
        setTimeout(focusContactName, 300);
    }

    function formatPhone(value) {
        const digits = (value || '').replace(/\D/g, '').slice(0, 11);
        if (!digits) return '';
        if (digits.length <= 2) return `(${digits}`;
        if (digits.length <= 6) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
        if (digits.length <= 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
        return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
    }

    if (phoneInput) {
        phoneInput.value = formatPhone(phoneInput.value);
        phoneInput.addEventListener('input', (event) => {
            event.target.value = formatPhone(event.target.value);
        });
    }
});
