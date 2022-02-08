Python tools for handling AMQP messaging
=========================================

* Based on pika
* Handle rabbitmq/AMQP messaging wihth asyncio

### Goals

* Get rid of  callback spaghetti code
* Wrap common patterns
* Handle reconnection on error  

### Example

```
    connection = AsyncConnection(host='my.rabbit.net') 
    pub = AsyncPublisher(connection=connection)
 
    await pub.connect(EXCHANGE)

    pub.publish(message) 
    
    pub.close()
    connection.close()
```

Or if you want to handle channel creation yourself:

```
# Create channel
channel = await connection.channel()

# Create exchange
await channel.exchange_declare(exchange='my.exchange', exchange_type='fanout')

...

```

### Requirements

- Python 3.5+


