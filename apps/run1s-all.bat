cd LP
python LPSolver.py player-1s.ini c1s.txt -t 0 %*
cd ..
cd ID3
python ID3-Gini.py player-1s.ini -t 0 %*
cd ..
python indextounitvector.py player-1s.ini -t 0 %*
python secretsanta.py player-1s.ini -t 0 %*
python sort.py player-1s.ini -t 0 %*

