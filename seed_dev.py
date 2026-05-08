import os
import sys

if os.getenv("ENVIRONMENT") != "development":
    print("Este script deve ser executado apenas em ambiente de desenvolvimento!")
    sys.exit(1)

from app.database import SessionLocal, engine, Base
from app.models import Client

clients_data = [
    {"name": "João Pedro Santos", "email": "joao.santos@email.com", "phone": "11999887766", "document": "12345678901", "address": "Rua das Flores, 100 - São Paulo, SP"},
    {"name": "Maria Oliveira Silva", "email": "maria.oliveira@email.com", "phone": "21988776655", "document": "23456789012", "address": "Av. Brasil, 500 - Rio de Janeiro, RJ"},
    {"name": "Carlos Eduardo Ferreira", "email": "carlos.ferreira@email.com", "phone": "31977665544", "document": "34567890123", "address": "Rua Tiradentes, 200 - Belo Horizonte, MG"},
    {"name": "Ana Paula Costa", "email": "ana.costa@email.com", "phone": "41966554433", "document": "45678901234", "address": "Alameda das Palmeiras, 150 - Curitiba, PR"},
    {"name": "Paulo Roberto Lima", "email": "paulo.lima@email.com", "phone": "51955443322", "document": "56789012345", "address": "Av. Ipiranga, 800 - Porto Alegre, RS"},
    {"name": "Juliana Martins Souza", "email": "juliana.souza@email.com", "phone": "61944332211", "document": "67890123456", "address": "Rua 7 de Setembro, 300 - Brasília, DF"},
    {"name": "Roberto Carlos Almeida", "email": "roberto.almeida@email.com", "phone": "71933221100", "document": "78901234567", "address": "Av. Paz, 250 - Salvador, BA"},
    {"name": "Patricia Rodrigues Gomes", "email": "patricia.gomes@email.com", "phone": "81922110099", "document": "89012345678", "address": "Rua Central, 450 - Recife, PE"},
    {"name": "Fernando Henrique Silva", "email": "fernando.silva@email.com", "phone": "91911009988", "document": "90123456789", "address": "Av. Fernandes Lima, 600 - Maceió, AL"},
    {"name": "Cristina Beatriz Nunes", "email": "cristina.nunes@email.com", "phone": "85990098877", "document": "01234567890", "address": "Rua das Dunas, 350 - Fortaleza, CE"},
    {"name": "Ricardo Mendes Pereira", "email": "ricardo.pereira@email.com", "phone": "88998877665", "document": "12345678902", "address": "Av.Beira Mar, 700 - Natal, RN"},
    {"name": "Luciana Vieira Cardoso", "email": "luciana.cardoso@email.com", "phone": "83987766554", "document": "23456789013", "address": "Rua das Acácias, 180 - João Pessoa, PB"},
    {"name": "Marcos Antonio Oliveira", "email": "marcos.oliveira@email.com", "phone": "85976654343", "document": "34567890124", "address": "Av. Jerônimo, 400 - Aracaju, SE"},
    {"name": "Sandra Maria Santos", "email": "sandra.santos@email.com", "phone": "79965543232", "document": "45678901235", "address": "Rua do Sol, 550 - Teresina, PI"},
    {"name": "Diego Fernando Rocha", "email": "diego.rocha@email.com", "phone": "86954432121", "document": "56789012346", "address": "Av.Universitária, 650 - Teresina, PI"},
    {"name": "Renata Cristina Lopes", "email": "renata.lopes@email.com", "phone": "85943321010", "document": "67890123457", "address": "Rua das Mangueiras, 250 - São Luís, MA"},
    {"name": "Gustavo Henrique Souza", "email": "gustavo.souza@email.com", "phone": "98932210999", "document": "78901234568", "address": "Av. Alexandre, 500 - Imperatriz, MA"},
    {"name": "Beatriz Aline Ferreira", "email": "beatriz.ferreira@email.com", "phone": "92921109888", "document": "89012345679", "address": "Rua das Palmeiras, 350 - Manaus, AM"},
    {"name": "Thiago Rafael Costa", "email": "thiago.costa@email.com", "phone": "92910098777", "document": "90123456780", "address": "Av. Pará, 800 - Belém, PA"},
    {"name": "Vanessa Patricia Lima", "email": "vanessa.lima@email.com", "phone": "91909987666", "document": "01234567891", "address": "Rua 13 de Maio, 420 - Belém, PA"},
    {"name": "Leandro Martins Silva", "email": "leandro.silva@email.com", "phone": "92998876555", "document": "12345678903", "address": "Av. Governador, 700 - Porto Velho, RO"},
    {"name": "Adriana Cristina Oliveira", "email": "adriana.oliveira@email.com", "phone": "95987765444", "document": "23456789014", "address": "Rua das Nacões, 150 - Rio Branco, AC"},
    {"name": "Alexandre Pereira Santos", "email": "alexandre.santos@email.com", "phone": "92976654333", "document": "34567890125", "address": "Av. Brasil, 600 - Campo Grande, MS"},
    {"name": "Fernanda Cristina Gomes", "email": "fernanda.gomes@email.com", "phone": "67965543222", "document": "45678901236", "address": "Rua São Paulo, 350 - Campo Grande, MS"},
    {"name": "Daniel Rodrigo Ferreira", "email": "daniel.ferreira@email.com", "phone": "67954432111", "document": "56789012347", "address": "Av. das Bandeiras, 800 - Cuiaba, MT"},
    {"name": "Simone Carla Rodrigues", "email": "simone.rodrigues@email.com", "phone": "64943321000", "document": "67890123458", "address": "Rua dos Ipês, 200 - Cuiaba, MT"},
    {"name": "Marcelo Silva Souza", "email": "marcelo.souza@email.com", "phone": "62932219988", "document": "78901234569", "address": "Av. Santos Dumont, 550 - Goiânia, GO"},
    {"name": "Andrea Cristina Lima", "email": "andrea.lima@email.com", "phone": "62921109877", "document": "89012345670", "address": "Rua 44, 400 - Anápolis, GO"},
    {"name": "Vinicius Henrique Santos", "email": "vinicius.santos@email.com", "phone": "61910098766", "document": "90123456781", "address": "Av. L Regional, 650 - Palmas, TO"},
    {"name": "Bruna Carla Oliveira", "email": "bruna.oliveira@email.com", "phone": "63909987655", "document": "01234567892", "address": "Rua 102, 300 - Palmas, TO"},
]

def seed_clients():
    db = SessionLocal()
    try:
        for data in clients_data:
            existing = db.query(Client).filter(Client.email == data["email"]).first()
            if not existing:
                client = Client(**data)
                db.add(client)
        
        db.commit()
        print(f"{len(clients_data)} clientes de desenvolvimento cadastrados com sucesso!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_clients()