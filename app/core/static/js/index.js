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

    function setActiveNavLink(link) {
        navLinks.forEach(nav => nav.classList.remove('active'));
        if (link) {
            link.classList.add('active');
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
        });
    });

    const contactForm = document.getElementById('contactForm');
    const contactStatus = document.getElementById('contactStatus');
    const contactNameInput = document.getElementById('name');

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
});
