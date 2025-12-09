document.addEventListener('DOMContentLoaded', () => {
    const currentYearEl = document.getElementById('currentYear');
    if (currentYearEl) {
        currentYearEl.textContent = new Date().getFullYear();
    }

    const companyForm = document.getElementById('companyForm');
    const companyStatus = document.getElementById('companyStatus');
    const companyState = document.getElementById('companyState');
    const companyCity = document.getElementById('companyCity');
    const companyPassword = document.getElementById('companyPassword');
    const companyPasswordConfirm = document.getElementById('companyPasswordConfirm');
    const togglePassword = document.getElementById('togglePassword');
    const togglePasswordConfirm = document.getElementById('togglePasswordConfirm');

    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    const navbarCollapse = document.getElementById('navbarNav');
    const bsCollapse = navbarCollapse && window.bootstrap
        ? new bootstrap.Collapse(navbarCollapse, { toggle: false })
        : null;

    const stateCityMap = {
        'AC': ['Rio Branco', 'Cruzeiro do Sul', 'Sena Madureira', 'Tarauacá'],
        'AL': ['Maceió', 'Arapiraca', 'Palmeira dos Índios', 'Rio Largo'],
        'AP': ['Macapá', 'Santana', 'Oiapoque', 'Laranjal do Jari'],
        'AM': ['Manaus', 'Parintins', 'Itacoatiara', 'Manacapuru', 'Coari'],
        'BA': ['Salvador', 'Feira de Santana', 'Vitória da Conquista', 'Ilhéus', 'Itabuna', 'Lauro de Freitas', 'Juazeiro'],
        'CE': ['Fortaleza', 'Juazeiro do Norte', 'Sobral', 'Maracanaú', 'Caucaia', 'Crato'],
        'DF': ['Brasília'],
        'ES': ['Vitória', 'Vila Velha', 'Cariacica', 'Serra', 'Linhares', 'Colatina'],
        'GO': ['Goiânia', 'Anápolis', 'Aparecida de Goiânia', 'Rio Verde', 'Luziânia', 'Valparaíso de Goiás'],
        'MA': ['São Luís', 'Imperatriz', 'Caxias', 'Timon', 'Bacabal'],
        'MT': ['Cuiabá', 'Várzea Grande', 'Rondonópolis', 'Sinop', 'Sorriso'],
        'MS': ['Campo Grande', 'Dourados', 'Três Lagoas', 'Corumbá', 'Naviraí', 'Ponta Porã'],
        'MG': ['Belo Horizonte', 'Uberlândia', 'Juiz de Fora', 'Contagem', 'Montes Claros', 'Uberaba', 'Betim'],
        'PA': ['Belém', 'Ananindeua', 'Santarém', 'Marabá', 'Parauapebas'],
        'PB': ['João Pessoa', 'Campina Grande', 'Patos', 'Santa Rita'],
        'PR': ['Curitiba', 'Londrina', 'Maringá', 'Cascavel', 'Ponta Grossa', 'Foz do Iguaçu'],
        'PE': ['Recife', 'Olinda', 'Jaboatão dos Guararapes', 'Caruaru', 'Petrolina'],
        'PI': ['Teresina', 'Parnaíba', 'Picos', 'Floriano'],
        'RJ': ['Rio de Janeiro', 'Niterói', 'Campos dos Goytacazes', 'Petrópolis', 'Volta Redonda', 'Duque de Caxias', 'Nova Iguaçu'],
        'RN': ['Natal', 'Mossoró', 'Parnamirim', 'Caicó'],
        'RS': ['Porto Alegre', 'Caxias do Sul', 'Pelotas', 'Santa Maria', 'Passo Fundo', 'Novo Hamburgo'],
        'RO': ['Porto Velho', 'Ji-Paraná', 'Ariquemes', 'Cacoal'],
        'RR': ['Boa Vista', 'Rorainópolis', 'Caracaraí'],
        'SC': ['Florianópolis', 'Joinville', 'Blumenau', 'Chapecó', 'Itajaí', 'Criciúma'],
        'SP': ['São Paulo', 'Guarulhos', 'Campinas', 'Santos', 'Ribeirão Preto', 'Sorocaba', 'São José dos Campos', 'Osasco', 'Santo André', 'São Bernardo do Campo'],
        'SE': ['Aracaju', 'Nossa Senhora do Socorro', 'Lagarto'],
        'TO': ['Palmas', 'Araguaína', 'Gurupi', 'Porto Nacional'],
    };

    function populateCities(uf) {
        if (!companyCity) return;
        companyCity.innerHTML = '<option value="" disabled selected>Selecione a cidade</option>';
        if (!uf || !stateCityMap[uf]) return;
        stateCityMap[uf]
            .slice()
            .sort()
            .forEach(city => {
                const opt = document.createElement('option');
                opt.value = city;
                opt.textContent = city;
                companyCity.appendChild(opt);
            });
    }

    function populateStates() {
        if (!companyState) return;
        companyState.innerHTML = '<option value="" disabled selected>Selecione o estado</option>';
        Object.keys(stateCityMap)
            .sort()
            .forEach(uf => {
                const opt = document.createElement('option');
                opt.value = uf;
                opt.textContent = uf;
                companyState.appendChild(opt);
            });
        const preset = companyState.dataset.selectedState || '';
        if (preset && stateCityMap[preset]) {
            companyState.value = preset;
            populateCities(preset);
            const presetCity = companyCity ? (companyCity.dataset.selectedCity || '') : '';
            if (companyCity && presetCity) {
                companyCity.value = presetCity;
            }
        } else {
            populateCities('');
        }
    }

    if (companyState) {
        companyState.addEventListener('change', (e) => {
            populateCities(e.target.value);
        });
    }

    function toggleVisibility(input, button) {
        if (!input || !button) return;
        button.addEventListener('click', () => {
            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            const icon = button.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-eye');
                icon.classList.toggle('fa-eye-slash');
            }
        });
    }

    toggleVisibility(companyPassword, togglePassword);
    toggleVisibility(companyPasswordConfirm, togglePasswordConfirm);

    if (companyForm) {
        companyForm.addEventListener('submit', (e) => {
            if (companyPassword && companyPasswordConfirm && companyPassword.value !== companyPasswordConfirm.value) {
                e.preventDefault();
                companyStatus.textContent = 'As senhas não conferem.';
                companyStatus.className = 'text-center mt-3 text-danger';
                return;
            }
            if (companyStatus) {
                companyStatus.textContent = '';
                companyStatus.className = '';
            }
        });
    }

    populateStates();

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
});
