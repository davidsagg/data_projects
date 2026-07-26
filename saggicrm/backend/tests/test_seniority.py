import pytest

from src.services.seniority import (
    ASSISTANT,
    C_LEVEL,
    DIRECTOR,
    MANAGER,
    SPECIALIST,
    UNCLASSIFIED,
    classify_seniority,
)


@pytest.mark.parametrize(
    "position,expected",
    [
        ("CEO", C_LEVEL),
        ("Chief Executive Officer", C_LEVEL),
        ("Founder & CEO", C_LEVEL),
        ("Fundador", C_LEVEL),
        ("Sócio-diretor", C_LEVEL),
        ("VP of Engineering", C_LEVEL),
        ("Director of Product", DIRECTOR),
        ("Diretora de Operações", DIRECTOR),
        ("Head of Sales", DIRECTOR),
        ("Product Manager", MANAGER),
        ("Gerente de Projetos", MANAGER),
        ("Team Lead", MANAGER),
        ("Coordenador de TI", MANAGER),
        ("Software Engineer", SPECIALIST),
        ("Analista de Sistemas", SPECIALIST),
        ("Data Scientist", SPECIALIST),
        ("Consultor Sênior", SPECIALIST),
        ("Marketing Intern", ASSISTANT),
        ("Estagiária de RH", ASSISTANT),
        ("Assistente Administrativo", ASSISTANT),
        ("", UNCLASSIFIED),
        (None, UNCLASSIFIED),
        ("Owner of a small bakery", C_LEVEL),
    ],
)
def test_classify_seniority(position, expected):
    assert classify_seniority(position) == expected


def test_assistant_director_lands_on_director_not_assistant():
    assert classify_seniority("Assistant Director of Marketing") == DIRECTOR


def test_engineering_manager_lands_on_manager_not_specialist():
    assert classify_seniority("Engineering Manager") == MANAGER


def test_product_owner_is_not_c_level():
    assert classify_seniority("Gerente de Produto | Product Owner | Produtos de IA") == MANAGER
    assert classify_seniority("Product Owner") == UNCLASSIFIED


def test_hr_business_partner_is_not_c_level():
    assert classify_seniority("HR Business Partner") == UNCLASSIFIED


def test_law_firm_partner_is_still_c_level():
    assert classify_seniority("Partner at Smith & Associates") == C_LEVEL
    assert classify_seniority("Sócio-fundador") == C_LEVEL
