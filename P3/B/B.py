# -*- coding: utf-8 -*-
"""
Autores: Luis M. Costero Valero & Jesús Doménech Arellano
Grupo 04

Este código es fruto ÚNICAMENTE del trabajo de sus miembros. Declaramos no 
haber colaborado de ninguna manera con otros grupos, haber compartido el ćodigo 
con otros ni haberlo obtenido de una fuente externa.
"""
import pymongo
from pymongo import MongoClient
from datetime import datetime
from bson import json_util
from bson import ObjectId
import json

#################################################################
## Es necesario añadir los parámetros adecuados a cada función ##
#################################################################

client = MongoClient('localhost',27017)
db = client['sgdi_grupo04']

# 1. Añadir un usuario
def insert_user(alias, nombre, apellidos, calle, numero, ciudad, pais,
                experiencia ):

    user = createUser(alias, nombre, apellidos, calle, numero, ciudad, pais, experiencia) 
    try:
        ret = db.usuarios.insert_one(user)
        return json_util.dumps({"inserted_id":ret.inserted_id})
    except Exception as e:
        return json_util.dumps({"error":str(e)})
 

# 2. Actualizar un usuario
def update_user(alias, nombre, apellidos, calle, numero, ciudad, pais,
                experiencia, fecha=None):

    user = createUser(alias, nombre, apellidos, calle, numero, ciudad,
                      pais, experiencia, fecha)
    try:
        ret = db.usuarios.update_one({"alias": alias}, {"$set":user})
        return json_util.dumps({"modified_count": ret.modified_count})
    except Exception as e:
        return json_util.dumps({"error":str(e)})


# 3. Añadir una pregunta
def add_question(titulo, alias, texto, tags, fecha=None):

    question = createQuestion(titulo, alias, texto, tags, fecha)
    try:
        if existsUser(alias):
            id = db.preguntas.insert_one(question).inserted_id
            return json_util.dumps({"inserted_id": id})
        else:
            return json_util.dumps({"error": "User does not exists"})
    except Exception as e:
        return json_util.dumps({"error":str(e)})


# 4. Añadir una respuesta a una pregunta.
def add_answer(pregunta_id, alias, texto, fecha=None):
    try:
        if existsUser(alias):
            if existsPregunta(pregunta_id):
                #1.- Insertamos la respuesta y guardamos su id
                answer = createAnswer(pregunta_id, alias, texto, fecha)

                id = db.respuestas.insert_one(answer).inserted_id
                #2.- Guardamos la referencia en la pregunta para poder acceder despues
                db.preguntas.update_one({"_id": pregunta_id},
                                        {"$push" : {"respuestas": id} })
                return json_util.dumps({"inserted_id": id})
            else:
                return json_util.dumps({"error": "Question does not exists"})
        else:
            return json_util.dumps({"error": "User does not exists"})

    except Exception as e:
        return json_util.dumps({"error":str(e)})

# 5. Comentar una respuesta.
def add_comment(respuesta_id, alias, texto, fecha=None):
    comment = createComment(alias, texto, fecha=None)
    try:
        if existsUser(alias):
            if existsAnswer(respuesta_id):
                id = db.respuestas.update_one({"_id":respuesta_id},
                                              {"$push": { "comentarios" : comment}})

                return json_util.dumps({"modified_count": id.modified_count})
            else:
                return json_util.dumps({"error": "Answer does not exists"})
        else:
            return json_util.dumps({"error": "User does not exists"})

    except Exception as e:
        return json_util.dumps({"error":str(e)})


# 6. Puntuar una respuesta.
def score_answer(respuesta_id, voto, alias):
    """ Suponemos que el voto nos va a venir en formato +/- 1.
    """
    #1.- Incrementamos el voto en la colección de respuestas, y nos quedamos con
    # el id de la pregunta para poder acceder a su titulo
    if voto > 0 :
        campo_modificar = "votos_pos"
    else:
        campo_modificar = "votos_neg"
    
    try: 
        if existsUser(alias):
            if existsAnswer(respuesta_id):
                preg_id = db.respuestas.find_one_and_update(
                    {"_id":respuesta_id}, {"$inc": {campo_modificar : 1}},
                    {"_id":0, "pregunta_id":1})
            else:
                return json_util.dumps({"error": "Answer does not exists"})
        else:
            return json_util.dumps({"error": "User does not exists"})
    except Exception as e:
        return json_util.dumps({"error":str(e)})

    preg_id=preg_id["pregunta_id"]
    
    
    #2.- Conseguimos el titulo de la pregunta
    titulo = db.preguntas.find_one({"_id": preg_id}, 
                                   {"_id":0, "titulo":1})["titulo"]

    #3.- Insertamos el voto en su colección
    score = createScore(respuesta_id, voto, alias, titulo)
    try:
        id = db.votos.insert_one(score).inserted_id

        return json_util.dumps({"inserted_id": id})
    except Exception as e:
        return json_util.dumps({"error":str(e)})



# 7. Modificar una puntuacion de buena a mala o viceversa.
def update_score(voto_id):
    """ Modificamos la puntuacion multiplicando por -1. Cogemos la anterior para
    saber como modificar la colección de respuestas
    """
    try:
        ret1 = db.votos.find_one_and_update(
            {"_id": voto_id}, {"$mul" : { "voto" : -1 }},
            {"_id":0, "respuesta_id": 1, "voto":1})

        if ret1 is None:
            return json_util.dumps({"modified_count" : 0})
        #por defecto, devuelve el valor que había antes de actualizar
        if ret1["voto"] > 0 :
            inc = "votos_neg"
            dec = "votos_pos"
        else:
            inc = "votos_pos"
            dec = "votos_neg"

        ret2 = db.respuestas.update_one({"_id": ret1["respuesta_id"]},
                                        {"$inc": {inc : 1, dec : -1}})


        return json_util.dumps({"modified_count" : ret2.modified_count})
    except Exception as e:
        return json_util.dumps({"error":str(e)})


# 8. Borrar una pregunta junto con todas sus respuestas, comentarios y 
# puntuaciones
def delete_question(pregunta_id):
    #1.- Borramos la pregunta, y nos quedamos con el array de respuestas.
    resp = db.preguntas.find_one_and_delete({"_id":pregunta_id},
                                            {"_id": 0, "respuestas":1})
    if resp is None:
        return json_util.dumps({
            "deleted_questions":0,
            "deleted_answers": 0,
            "deleted_scores": 0
        })
    resp = resp["respuestas"]
    
    if(len(resp) == 0):
        return json_util.dumps({
            "deleted_questions":1,
            "deleted_answers": 0,
            "deleted_scores": 0
        })
    
    #2.- Con ese array, borramos todas las respuestas
    respDel = db.respuestas.delete_many({"_id": {"$in": resp}}).deleted_count

    #3.- Con ese array, borramos todos los votos
    votDel = db.votos.delete_many({"respuesta_id" : {"$in":resp}}).deleted_count
    
    return json_util.dumps({
        "deleted_questions":1,
        "deleted_answers": respDel,
        "deleted_scores": votDel
    })


# 9. Visualizar una determinada pregunta junto con todas sus contestaciones
# y comentarios. A su vez las contestaciones vendran acompañadas de su
# numero de puntuaciones buenas y malas.
def get_question(pregunta_id):
    #1.- Conseguir la pregunta
    question = db.preguntas.find_one({"_id": pregunta_id})
    if question is None:
        return json_util.dumps({"error":"Question does not exists"})
    #2.- Conseguir todos las contestaciones y comentarios
    answers = db.respuestas.find({"_id": { "$in": question["respuestas"]}},
                                 {"pregunta_id": 0 })
    
    return json_util.dumps({"question" : question,
                            "answers" : answers})


# 10. Buscar preguntas con unos determinados tags y mostrar su titulo, su autor
# y su numero de contestaciones.
def get_question_by_tag(tags):

    if not isinstance(tags, list):
        tags = [tags]

    #Para realizar la consulta y quedarnos solamente con los campos que queremos,
    #y además contar el número de elementos, realizamos un aggregation pipeline

    pipeline = [
        {"$match": {"tags": {"$all": tags}}},
        {"$project": {
            "alias": 1,
            "titulo": 1,
            "_id": 0,
            "num_contestaciones": { "$size": "$respuestas"}
           }
         }
    ]
         
    questions = db.preguntas.aggregate(pipeline)

    return json_util.dumps({"questions":questions})


# 11. Ver todas las preguntas o respuestas generadas por un determinado usuario.
def get_entries_by_user(alias):
    """ Para optimizar esta función, sería interesante considerar la posibilidad
    de poner un índice sobre el campo "alias" tanto de la colección de
    preguntas como de respuestas
    """
    if not existsUser(alias):
        return json_util.dumps({"error": "User does not exists"})

    ret = {"preguntas": [], "respuestas": [] }
    #1.- Conseguir las preguntas
    ret["preguntas"] = db.preguntas.find({"alias": alias})
    
    #2.- Conseguir las respuestas
    ret["respuestas"] = db.respuestas.find({"alias": alias})
    
    return json_util.dumps(ret)


# 12. Ver todas las puntuaciones de un determinado usuario ordenadas por 
# fecha. Este listado debe contener el tıtulo de la pregunta original 
# cuya respuesta se puntuo.
def get_scores(alias):
    if not existsUser(alias):
        return json_util.dumps({"error": "User does not exists"})

    votos = db.votos.find({"alias":alias},{"_id":0}).sort("fecha_creacion",pymongo.DESCENDING)
    
    return json_util.dumps({"scores": votos})


# 13. Ver todos los datos de un usuario.
def get_user(alias):
    user = db.usuarios.find_one({"alias":alias}, {"_id": 0})
    if user is None:
        return json_util.dumps({"error": "User does not exists"})
    return json_util.dumps(user)


# 14. Obtener los alias de los usuarios expertos en un determinado tema.
def get_uses_by_expertise(topic):
    
    alias = db.usuarios.find({"experiencia":topic},  {"alias": 1, "_id": 0})
    return json_util.dumps({"usuarios":alias})


# 15. Visualizar las n preguntas mas actuales ordenadas por fecha, incluyendo
# el numero de contestaciones recibidas.
def get_newest_questions(n):
    #utilizando un aggregation pipeline para realizar el proceso
    pipeline = [
        
        {"$sort": { "fecha_creacion" : -1}},
        {"$limit": n},      
        {"$project": {
            "_id": 0,
            "alias": 1,
            "titulo": 1,
            "tags": 1,
            "fecha_creacion": 1,
            "num_contestaciones": { "$size": "$respuestas"}
        }
     }
    ]

    questions = db.preguntas.aggregate(pipeline)

    return json_util.dumps({"questions":questions})


# 16. Ver n preguntas sobre un determinado tema, ordenadas de mayor a menor por
# numero de contestaciones recibidas.
def get_questions_by_tag(n, topic):
    #utilizando un aggregation pipeline para realizar el proceso.
    if not isinstance(topic, list):
        topic = [topic]
    
    pipeline = [
        {"$match": { "tags" : {"$all" : topic}}},
        {"$project" : {
            "_id": 1,
            "tags" : 1,
            "fecha_creacion":1,
            "alias": 1,
            "titulo": 1,
            "texto": 1,
            "num_contestaciones":{"$size": "$respuestas"} }},
        {"$sort": {"num_contestaciones": -1}},
        {"$limit": n}
    ]

    questions = db.preguntas.aggregate(pipeline)

    return json_util.dumps({"questions":questions})
    
################################################################################
################  FUNCIONES AUXILIARES CON CONEXION ############################
################################################################################

def existsUser(alias):
    try:
        ret = db.usuarios.find_one({"alias":alias},{"alias":1})
        return not (ret is None)
    except Exception as e:
        return False



def existsPregunta(id):
    try:
        ret = db.preguntas.find_one({"_id":id},{"_id":1})
        return not (ret is None)
    except Exception as e:
        return False

def existsAnswer(id):
    try:
        ret = db.respuestas.find_one({"_id":id},{"_id":1})
        return not (ret is None)
    except Exception as e:
        return False


################################################################################
################ FUNCIONES AUXILIARES SIN CONEXION #############################
################################################################################


#Dados los campos de una direccion, devuelve el objeto para insertar
def createDirection(calle, numero, ciudad, pais):
    return {"calle": calle,
            "numero": numero,
            "ciudad": ciudad,
            "pais": pais}

#Crea un usuario para insertar en la bd. si la fecha en nula, pone la actual
def createUser(alias, nombre, apellidos, calle, numero, ciudad, pais,
               experiencia, fecha=None):
    dir = createDirection(calle, numero, ciudad, pais)

    if not isinstance(experiencia, list):
        experiencia = [experiencia]

    if fecha is None:
        fecha = datetime.utcnow()

    return {"alias": alias,
            "nombre": nombre,
            "apellidos": apellidos,
            "direccion": dir,
            "experiencia": experiencia,
            "fecha_creacion": fecha
    }


#Crea una pregunta a partir de su contenido dado por parámetro
def createQuestion( titulo, alias, texto, tags, fecha=None):
    if not isinstance(tags, list):
        tags = [tags]
    if fecha is None:
        fecha = datetime.utcnow()

    return {"titulo": titulo,
            "alias": alias,
            "texto": texto,
            "tags" : tags,
            "fecha_creacion": fecha,
            "respuestas" : []
        }


#Dados los datos de una respuesta, crea el objeto a insertar en la bd
def createAnswer(pregunta_id, alias, texto, votos_pos=None, votos_neg=None, fecha=None):
    if fecha is None:
        fecha = datetime.utcnow()
    if votos_pos is None:
        votos_pos = 0
    if votos_neg is None:
        votos_neg = 0
    

    return {"pregunta_id" : pregunta_id,
            "alias" : alias,
            "texto" : texto,
            "votos_pos" : votos_pos,
            "votos_neg" : votos_neg,
            "fecha_creacion" : fecha,
            "comentarios" : []
    }


#Dados los datos de un comentario, crea el objeto para insertar en la bd
def createComment(alias, texto, fecha=None) :
    if fecha is None:
        fecha = datetime.utcnow()

    return {"alias": alias,
            "texto": texto,
            "fecha_creacion": fecha
    }
    

#Dados los datos de un voto, crea el objeto para insertalo en la bd
def createScore(respuesta_id, voto, alias, titulo, fecha = None):
    if fecha is None:
        fecha = datetime.utcnow()

    return {"respuesta_id": respuesta_id,
            "voto": voto,
            "alias": alias,
            "titulo": titulo,
            "fecha_creacion": fecha
    }

