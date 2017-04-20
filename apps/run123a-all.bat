cd LP
start python LPsolver.py player-3.ini c3.txt %*
start python LPsolver.py player-2.ini c2.txt %* 
python LPsolver.py player-1.ini c1.txt %*
cd ..

cd ID3
start python ID3-Gini.py player-3.ini %*
start python ID3-Gini.py player-2.ini %*
python ID3-Gini.py player-1.ini %*
cd ..

start python indextounitvector.py player-3.ini %*
start python indextounitvector.py player-2.ini %*
python indextounitvector.py player-1.ini %*

start python secretsanta.py player-3.ini %*
start python secretsanta.py player-2.ini %*
python secretsanta.py player-1.ini %*

start python sort.py player-3.ini %*
start python sort.py player-2.ini %*
python sort.py player-1.ini %*

start python millionaires.py player-3.ini %*
start python millionaires.py player-2.ini %*
python millionaires.py player-1.ini %*

start python multiply.py player-3.ini 7 %*
start python multiply.py player-2.ini 7 %*
python multiply.py player-1.ini 7 %*

start python two-fields.py player-3.ini %*
start python two-fields.py player-2.ini %*
python two-fields.py player-1.ini %*

