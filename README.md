# Deye Hard Backend


## Setup

Um über die Influx API User, Organisations und Buckets erstellen zu können, wird ein Operator Token benötigt. Dieser muss mit dem Nachfolgendem 
Befehl innerhalb des Docker containers der Influx erzeugt werden und anschließend in die ENV-Datei `backend.env` in der Umgebungsvariable `INFLUX_OPERATOR_TOKEN` Datei ergänzt werden.
    
    docker-compose up -d influxdb
    $ influx config create --config-name wtf --host-url http://localhost:8086 --org wtf --token <init_admin_token> --active
    
    $ influx auth create --org wtf --operator
    BGjD1aQT6_5ymaXBDek9lhtQaxXlI-IUQTSXOR1ZqyPt7OkBsTlo-cp5zsw4ZmLzdh71dgGDT8ooBPZFuopT2Q==

    $ docker-compose down

    $ echo 'INFLUX_OPERATOR_TOKEN="BGjD1aQT6_5ymaXBDek9lhtQaxXlI-IUQTSXOR1ZqyPt7OkBsTlo-cp5zsw4ZmLzdh71dgGDT8ooBPZFuopT2Q=="' >> backend.env

    $ docker-compose up -d

